/* Sign in with GitHub for the submit page (https://prosperostore.net/submit/).

   The page reads a developer's repository through GitHub's API, which lets 60 requests an hour through
   without sign-in and 5,000 with it. A browser can't finish GitHub's OAuth flow alone (it needs the app's
   secret, and GitHub's token endpoint doesn't allow browser requests), so this Worker does that one step:

     GET /login?origin=<site>   sends the visitor to GitHub, remembering the state and the site in a cookie
     GET /callback              takes GitHub's code, trades it for a token, hands the token to the site's
                                window with postMessage, and closes itself

   It asks GitHub for no scopes (a token that can only read what is public), keeps nothing (no database, no
   logs of tokens or names) and only answers to the sites in ALLOWED_ORIGINS. Settings, in wrangler.toml:
   CLIENT_ID, ALLOWED_ORIGINS; secret: CLIENT_SECRET. See README.md. */

const COOKIE = "login";
const GITHUB = "https://github.com/login/oauth";

function allowedOrigins(env) {
  return String(env.ALLOWED_ORIGINS || "").split(",").map((origin) => origin.trim()).filter(Boolean);
}

function random() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function plain(message, status) {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" },
  });
}

function cookieValue(request) {
  for (const part of String(request.headers.get("Cookie") || "").split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === COOKIE) return rest.join("=");
  }
  return "";
}

const forget = `${COOKIE}=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax`;

/* The page that hands the answer to the window that opened this one, only ever to `origin`. */
function handOver(origin, message) {
  const nonce = random();
  // "<" is escaped so no value can close the script element.
  const data = JSON.stringify(message).replace(/</g, "\\u003c");
  const target = JSON.stringify(origin).replace(/</g, "\\u003c");
  const body = `<!doctype html><meta charset="utf-8"><title>GitHub</title><p>You can close this window.</p>
<script nonce="${nonce}">(function () {
  if (window.opener) window.opener.postMessage(${data}, ${target});
  window.close();
})();</script>`;
  return new Response(body, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": `default-src 'none'; script-src 'nonce-${nonce}'`,
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      "Set-Cookie": forget,
    },
  });
}

function login(url, env) {
  const origin = url.searchParams.get("origin") || "";
  if (!allowedOrigins(env).includes(origin)) return plain("This site is not allowed to sign in here.", 400);
  const state = random();
  const authorize = new URL(`${GITHUB}/authorize`);
  authorize.searchParams.set("client_id", env.CLIENT_ID);
  authorize.searchParams.set("redirect_uri", `${url.origin}/callback`);
  authorize.searchParams.set("state", state);
  authorize.searchParams.set("allow_signup", "false");     // no scope: the token can read only what is public
  return new Response(null, {
    status: 302,
    headers: {
      Location: authorize.href,
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
      "Set-Cookie": `${COOKIE}=${state}.${encodeURIComponent(origin)}; Max-Age=600; Path=/; HttpOnly; Secure; SameSite=Lax`,
    },
  });
}

async function callback(request, url, env) {
  // The cookie is "<state>.<origin>": the state is hex, so the first dot ends it (the origin has dots too).
  const saved = cookieValue(request);
  const dot = saved.indexOf(".");
  const state = dot < 0 ? "" : saved.slice(0, dot);
  const encoded = dot < 0 ? "" : saved.slice(dot + 1);
  let origin = "";
  try { origin = decodeURIComponent(encoded || ""); } catch (error) { /* rejected below */ }
  if (!state || state !== url.searchParams.get("state") || !allowedOrigins(env).includes(origin)) {
    return plain("The sign-in expired or did not start here. Close this window and try again.", 400);
  }
  const code = url.searchParams.get("code");
  if (!code) return handOver(origin, { type: "github-login", error: "denied" });
  let token = "";
  try {
    const answer = await fetch(`${GITHUB}/access_token`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json", "User-Agent": "prosperostore-login" },
      body: JSON.stringify({
        client_id: env.CLIENT_ID, client_secret: env.CLIENT_SECRET, code, redirect_uri: `${url.origin}/callback`,
      }),
    });
    const data = await answer.json();
    token = typeof data.access_token === "string" ? data.access_token : "";
  } catch (error) { /* reported to the page */ }
  return handOver(origin, token ? { type: "github-login", token } : { type: "github-login", error: "failed" });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET") return plain("Method not allowed", 405);
    if (url.pathname === "/login") return login(url, env);
    if (url.pathname === "/callback") return callback(request, url, env);
    return plain("Not found", 404);
  },
};
