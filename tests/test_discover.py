import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catalog import draft as draft_module
from catalog.discover import (clean_text, discover, first_paragraph, previous_state, pull_request_text, read_ignore,
                              read_scope,
                              render, shorten)

from helpers import record, write_record

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + (512).to_bytes(4, "big") * 2
ZIP = {"name": "App.zip", "size": 10, "digest": "sha256:" + "e" * 64}


def param(titleid, name):
    return {"titleId": titleid, "localizedParameters": {"defaultLanguage": "en-US", "en-US": {"titleName": name}}}


class FakeGitHub:
    """Public GitHub as the discovery job sees it: search hits, releases, trees and files."""

    def __init__(self):
        self.code = {"filename:param.json path:sce_sys PPSA": ["Dev/Player", "Dev/Unreleased", "example/example-app"]}
        self.repos = {"prospero in:name": [{"full_name": "Other/Desktop-Tool", "archived": False}]}
        self.owner = {"dev": [{"full_name": "Dev/Chess", "pushed_at": "2099-01-01T00:00:00Z"}]}
        self.releases_by_repo = {
            "Dev/Player": [{"tag_name": "v1.0", "assets": [ZIP], "published_at": "2026-09-01T00:00:00Z",
                            "body": ""}],
            "Dev/Chess": [{"tag_name": "2.0", "assets": [dict(ZIP, name="Chess-FAKE07001.zip",
                                                               digest="sha256:" + "f" * 64)],
                           "published_at": "2026-09-02T00:00:00Z", "body": ""}],
            "Other/Desktop-Tool": [{"tag_name": "v3", "assets": [dict(ZIP, name="tool-win.zip")], "body": ""}],
        }
        self.params = {"Dev/Player": param("PPSA07000", "Media Player @everyone")}
        self.meta = {"Dev/Player": {"description": "A video player for PS5 with hardware decoding. 🎬"}}

    def search(self, kind, query, page=1, sort=""):
        if kind == "code":
            return {"items": [{"repository": {"full_name": r}} for r in self.code.get(query, [])]}
        return {"items": self.repos.get(query, [])}

    def owner_repos(self, owner):
        return self.owner.get(owner, [])

    def releases(self, owner, name):
        return self.releases_by_repo.get(f"{owner}/{name}", [])

    def repo(self, owner, name):
        full = f"{owner}/{name}"
        return {"full_name": full, "private": False, "archived": False, "fork": False,
                "license": {"spdx_id": "MIT"}, **self.meta.get(full, {})}

    def tree(self, owner, name, ref):
        return ["sce_sys/param.json", "sce_sys/icon0.png"] if f"{owner}/{name}" in self.params else ["README.md"]

    def file_text(self, owner, name, path, ref):
        full = f"{owner}/{name}"
        return json.dumps(self.params[full]) if path.endswith("param.json") else "# Title\n\nSome README text here."

    def user(self, login):
        return {"name": None}


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.apps = Path(self.tmp.name) / "apps"
        write_record(self.apps, record())   # example/example-app, owner "example"
        for patcher in (mock.patch.object(draft_module.artifacts, "fetch_small", lambda url, limit: PNG),):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def run_discover(self, github=None, ignore=frozenset()):
        github = github or FakeGitHub()
        # Dev has a strong candidate, so Dev's other repositories are scanned too.
        github.owner.setdefault("example", [])
        return {c.repo: c for c in discover(github, self.apps, set(ignore), sleep=lambda s: None).candidates}

    def test_statuses(self):
        found = self.run_discover()
        self.assertEqual(found["example/example-app"].status, "listed")
        self.assertEqual(found["Dev/Player"].status, "ready")
        self.assertEqual(found["Dev/Unreleased"].status, "unreleased")
        self.assertEqual(found["Dev/Chess"].status, "review")      # no param.json, but a title ID in the file name
        self.assertIn("FAKE07001 in the release", found["Dev/Chess"].signals)
        self.assertIn("developer of a candidate", found["Dev/Chess"].signals)
        self.assertEqual(found["Other/Desktop-Tool"].status, "not a native title")

    def test_ignore_list(self):
        found = self.run_discover(ignore={"dev/player"})
        self.assertEqual(found["Dev/Player"].status, "ignored")

    def test_scan_scope(self):
        github = FakeGitHub()
        github.owner.setdefault("example", [])
        result = discover(github, self.apps, set(), sleep=lambda s: None,
                          out_of_scope=read_scope("@Dev, someone-else"))
        self.assertEqual({c.repo for c in result.candidates}, {"example/example-app", "Other/Desktop-Tool"})
        self.assertNotIn("dev", render(result).casefold().replace("developer", ""))
        self.assertEqual(result.warnings, [])
        self.assertEqual(read_scope(""), set())

    def test_ready_record_is_complete_with_labelled_guesses(self):
        player = self.run_discover()["Dev/Player"]
        data = player.record
        self.assertEqual((data["titleid"], data["kind"], data["license"], data["version"]),
                         ("PPSA07000", "app", "MIT", "1.0"))
        self.assertEqual(data["description"], "A video player for PS5 with hardware decoding.")
        self.assertEqual(data["author"], "Dev")
        self.assertIn('guessed from the word "Media"', player.guesses[0])
        title, body = pull_request_text(player)
        self.assertEqual(title, "List Media Player @everyone by Dev")
        self.assertIn("sha256:" + "e" * 64, body)
        self.assertNotIn("@everyone", body)                         # mentions are broken in the body
        self.assertIn("close without merging", body)

    def test_report_marks_new_repositories_and_keeps_state(self):
        found = self.run_discover()
        result = mock.Mock(candidates=list(found.values()), warnings=[], examined=4, started="today")
        found["Dev/Player"].note = "#12 opened"
        first = render(result)
        self.assertNotIn("🆕 [", first)
        self.assertIn("#12 opened", first)
        self.assertEqual(previous_state(first), {"dev/player", "dev/chess", "dev/unreleased"})
        second = render(result, previous={"dev/player"})
        self.assertIn("🆕 [Dev/Chess]", second)
        self.assertNotIn("🆕 [Dev/Player]", second)

    def test_rejected_listing_is_hidden(self):
        found = self.run_discover()
        found["Dev/Player"].note = "rejected: a listing pull request was closed without merging"
        body = render(mock.Mock(candidates=list(found.values()), warnings=[], examined=4, started="today"))
        self.assertNotIn("[Dev/Player]", body)
        self.assertIn("1 app(s) not shown again", body)

    def test_desktop_builds_and_samples_need_review(self):
        github = FakeGitHub()
        github.releases_by_repo["Dev/Player"][0]["assets"] = [dict(ZIP, name="libplayer-linux-arm64.zip")]
        player = self.run_discover(github)["Dev/Player"]
        self.assertEqual(player.status, "review")
        self.assertIn("desktop build", player.draft.blockers[-1])
        self.assertIsNone(player.record)

    def test_guards_match_what_they_should(self):
        from catalog.discover import DESKTOP_BUILD, SAMPLE_FOLDER
        for name in ("tool-win64.zip", "app-linux-x64.zip", "Lib_macOS.zip", "setup.zip", "pkg-x86_64.zip"):
            self.assertTrue(DESKTOP_BUILD.search(name), name)
        urls = [json.loads(p.read_text(encoding="utf-8"))["artifact_url"]
                for p in (Path(__file__).resolve().parents[1] / "apps").glob("*.json")]
        listed = [url.rsplit("/", 1)[-1] for url in urls if url]   # reservations have no file yet
        for name in listed + ["kodi-ps5-PPSA99420-0.8.1.zip", "EVOPlayer-v0.10.0-PPSA99039.ffpfsc"]:
            if name:
                self.assertFalse(DESKTOP_BUILD.search(name), name)
        self.assertTrue(SAMPLE_FOLDER.search("src/HomebrewTest/sce_sys/param.json"))
        self.assertTrue(SAMPLE_FOLDER.search("samples/cube/sce_sys/param.json"))
        self.assertFalse(SAMPLE_FOLDER.search("sce_sys/param.json"))
        self.assertFalse(SAMPLE_FOLDER.search("ps5/sce_sys/param.json"))
        self.assertFalse(SAMPLE_FOLDER.search("projects/evoplayer/sce_sys/param.json"))

    def test_text_helpers(self):
        readme = ("<p align=center><img src=x></p>\n\n# App\n\n[![badge](b)](l)\n\n"
                  "**A media player** for [PS5](https://x).\nSecond line.\n\n## More")
        self.assertEqual(clean_text(first_paragraph(readme)), "A media player for PS5. Second line.")
        self.assertEqual(shorten("One sentence that is long enough. " * 10, 60), "One sentence that is long enough.")
        self.assertTrue(shorten("word " * 100, 50).endswith("…"))
        self.assertLessEqual(len(shorten("word " * 100, 50)), 50)

    def test_read_ignore(self):
        path = Path(self.tmp.name) / "ignore.txt"
        path.write_text("# comment\nDev/Player   # a template\n\n", encoding="utf-8")
        self.assertEqual(read_ignore(path), {"dev/player"})
        self.assertEqual(read_ignore(Path(self.tmp.name) / "missing.txt"), set())


if __name__ == "__main__":
    unittest.main()
