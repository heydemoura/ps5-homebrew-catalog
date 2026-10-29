# Sign in with GitHub (optional)

A small Cloudflare Worker that lets the [submit page](https://prosperostore.net/submit/) sign a developer in
with GitHub. Signing in raises GitHub's request limit for the page from 60 to 5,000 an hour. It is optional:
without it the page works for everyone, and the button stays hidden until the site is told where the Worker is.

It asks GitHub for **no permissions** (the token can read only what is public), keeps **nothing** (no database,
no logs of tokens or names), and only answers sites listed in `ALLOWED_ORIGINS`. The token goes to the page
with `postMessage`, to the exact site that asked, and the page keeps it for that browser tab only.

## Set it up (free: Cloudflare's Workers plan and a GitHub OAuth App cost nothing)

1. **Create the OAuth App** at <https://github.com/settings/developers> → *OAuth Apps* → *New OAuth App*:
   - Application name: `ProsperoStore catalog`
   - Homepage URL: `https://prosperostore.net`
   - Authorization callback URL: `https://<your-worker>.workers.dev/callback` (you learn the address in step 2;
     come back and edit it)
   - Create it, copy the **Client ID**, and generate a **Client secret**.
2. **Create the Worker** at <https://dash.cloudflare.com> → *Workers & Pages* → *Create* → *Hello World* → name it
   `prosperostore-login` → *Deploy* → *Edit code*, replace the code with `src/index.js` and *Deploy*.
   (With the command line instead: `cd worker/github-login && npx wrangler deploy`.)
3. **Settings → Variables and Secrets** of the Worker:
   - `CLIENT_ID` (text): the Client ID.
   - `ALLOWED_ORIGINS` (text): `https://prosperostore.net`. To test on your computer, add
     `,http://localhost:8000`.
   - `CLIENT_SECRET` (**secret**): the Client secret.
4. Put the Worker's address (`https://prosperostore-login.<account>.workers.dev`, no slash at the end) in
   `GITHUB_LOGIN_URL` in `catalog/site.py`, and publish the site.

To stop using it: empty `GITHUB_LOGIN_URL` and delete the Worker. A token a visitor holds can be revoked at
<https://github.com/settings/applications>.
