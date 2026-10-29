# Metadata format

Each app is one UTF-8 JSON file at `apps/<TITLEID>.json` (or `apps/<TITLEID>-<owner>.json`, see [Shared title IDs](#shared-title-ids)), at most 8 KiB,
containing a single object with the twelve fields below, plus `icon_member` only
when the icon is [inside the release file](#icon-inside-the-release-file), and
`internalOnly` only when you want it ([see below](#internalonly)). No
field may be missing and no other fields are allowed. Values are non-empty
strings; only [reservations](#reservations-coming-soon) use `null`, and
`icon_url` when `icon_member` is present.

| Field | Max length | Rules |
| --- | ---: | --- |
| `titleid` | 9 | Four uppercase letters and five digits, e.g. `PPSA01234`. Custom prefixes such as `FAKE77031` are allowed, except `CUSA` (PS4) and `NPXS` (system); such an app is listed under `shared` in the API, which ProsperoStore before 1.000.110 does not show. Must equal the start of the filename (see [Shared title IDs](#shared-title-ids)), and should equal the app's `titleId` in `sce_sys/param.json`. `PPSA99999` is reserved. |
| `name` | 64 | Display name. Unique across the catalog, ignoring case. |
| `kind` | 4 | `app`, `game` or `tool`. |
| `category` | 16 | One of the keys under [Categories](#categories), such as `emulators` or `video`. |
| `description` | 200 | One short plain-text sentence. No Markdown or HTML; it is displayed as text. |
| `license` | 64 | SPDX identifier or expression (`GPL-3.0`, `MIT OR Apache-2.0`). Must agree with the license GitHub detects for `source_repo`. |
| `author` | 64 | Developer or publisher name, as you want it credited. |
| `version` | 32 | Version shown to users: the release tag in `artifact_url`, optionally without a leading `v` (tag `v0.2.0-alpha.1` → `0.2.0-alpha.1`). Letters, digits and `. + _ -`. Consoles find updates with the release's `contentVersion` instead, which the catalog reads from your repository; see [App versions](versioning.md). |
| `source_repo` | 200 | `https://github.com/<owner>/<repository>`, using GitHub's exact capitalization. Must be public. |
| `artifact_url` | 500 | `<source_repo>/releases/download/<tag>/<asset>` for a published release; the asset is a `.zip` of the app folder, the only [format](artifact-formats.md) accepted at the moment. Moving links such as `/releases/latest/download/` are rejected. Unique across the catalog. |
| `sha256` | 64 | SHA-256 of the artifact as 64 lowercase hex characters. Unique across the catalog. |
| `icon_url` | 500 | Direct HTTPS link ending in `.png`, `.jpg`, `.jpeg` or `.webp`, returning that image type, at most 2 MiB. Square; 512×512 recommended (the size of `sce_sys/icon0.png`), 256×256 at least. Larger images are scaled down to 512 px. Pin to a tag or commit. |

## internalOnly

Optional. Add `"internalOnly": true` when the app must live on the console's
internal storage (`/data/homebrew`). ProsperoStore then installs it there
whatever install location the user chose in its settings. It can be added to an
app that is already listed: from then on, new installs and updates are
downloaded to internal storage, even when the previous version is on another
drive. Once the new copy is in place, the store uninstalls the older one it
installed on that other drive (the app's saved data stays). The only accepted value is `true`; leave the field out, or remove it later, for the
normal behaviour (the location chosen in the store's settings). The API
repeats it in `apps/<ID>.json`.

## Categories

Every app is in exactly one category, the shelf it is shown on in the website
and the store. Pick the one people would look in first; a reviewer may ask you
to change it.

| `category` | Shown as | For |
| --- | --- | --- |
| `console-ports` | Console game ports | Games from consoles, rebuilt to run natively: decompilations and recompilations. They usually need your own game data. |
| `pc-ports` | PC game ports | Games that came from PC: released source code, open-source games and engine rewrites. |
| `homebrew-games` | Homebrew games | Games made for the PS5. |
| `emulators` | Emulators | Emulators and loaders for other systems. |
| `streaming` | Game streaming | Cloud gaming and remote play. |
| `video` | Video & TV | Video players, media centres, streaming services and their companions. |
| `music` | Music & audio | Music players, radio and audio services. |
| `ai` | AI | Language models and other AI that run on the console. |
| `utilities` | Utilities | Files, launchers, backups and system helpers. |
| `tools` | Tools & tests | Controller, screen and sound checks and tuning. |
| `showcases` | Showcases | Tech demos and kits for developers. |

## Reservations (coming soon)

A title ID can be reserved before its first release. A reservation has the same
twelve fields, with the release-specific ones empty:

| Field | In a reservation |
| --- | --- |
| `artifact_url` | `null`. This is what marks the record as a reservation. |
| `source_repo`, `icon_url`, `sha256` | Must be `null`. |
| `version`, `license` | `null`, or a value following the rules above. |
| `titleid`, `name`, `kind`, `category`, `description`, `author` | Required, same rules as above. |

`null` is allowed nowhere else. A reservation belongs to the GitHub account
that added it, and each account can hold at most 5. See
[Reserving a title ID](submitting.md#reserving-a-title-id).

## Icon inside the release file

A repository that does not commit `sce_sys/param.json` ships it only inside the
release ZIP, and often the icon too. For such an app `icon_url` is `null` and
`icon_member` names the icon in the ZIP, in the same folder as the `param.json`
(for example `PPSA01234/sce_sys/icon0.png`). The catalog reads that one file from
the ZIP without downloading the rest, and applies the same image rules as for
`icon_url`: PNG, JPEG or WebP, at most 2 MiB.

| Field | Rules |
| --- | --- |
| `icon_member` | Relative path inside the ZIP of `artifact_url`, ending in `.png`, `.jpg`, `.jpeg` or `.webp`. No leading `/`, empty or `.`/`..` parts, or backslashes. Needs a `.zip` release file. Absent in a reservation. |
| `icon_url` | Must be `null` when `icon_member` is present. |

A new release moves the icon with its file; the checks fail if the new ZIP does
not contain the member.

## Text rules

All values must be NFC-normalized Unicode without leading or trailing
whitespace. Control characters, line breaks, invisible formatting characters
(including bidirectional overrides and zero-width characters), private-use and
unassigned code points are rejected. This keeps names from being visually
spoofed and keeps records safe to render anywhere.

## JSON rules

- Duplicate keys are rejected, even with identical values.
- Values must be strings; numbers are rejected, and `null` is accepted only in
  reservations (and for `icon_url` beside an `icon_member`).
- Formatting is free, but the repository uses two-space indentation and field
  order as shown in the [README](../README.md#record-format).

## Why these fields

The record carries only what a person has to state and a maintainer has to
review: what the app is, and which exact file is listed. The sha256 is what
ties a reviewed listing to the bytes users download.

Everything a machine can read for itself stays out of the record. The download
size, the release date and the content version are added to the
[store API](api.md) by the build, from GitHub and from the app's repository, so
they can't disagree with the release. Release history and compatibility notes
stay in the developer's repository.

## Shared title IDs

Two different apps can end up with the same title ID, for example when both were
built from a template. The first one listed keeps `apps/<TITLEID>.json`. A later,
different app from another developer is listed as `apps/<TITLEID>-<owner>.json`,
where `<owner>` is the owner of its `source_repo`, in lowercase
(`apps/PPSA01234-janedoe.json`). The `titleid` field inside stays the plain
title ID.

- The filename without `.json` is the app's **id**. It is what the website and
  the [store API](api.md) use to address the app, and it never changes.
- A reservation always uses the plain title ID: it has no `source_repo` to take an
  owner from.
- A console holds one app per title ID. Installing one of two apps that share it
  replaces the other, and they share save data, so the API lists the other app in
  `conflicts_with` and a store should warn before installing.
- Prefer a unique title ID when you can: it is what the console sees, and it avoids
  the clash altogether.
