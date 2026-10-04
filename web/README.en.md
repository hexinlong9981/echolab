# web/ — Replay, eval dashboard and local live screen

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

> This is a translation; the Japanese version is canonical.

A web UI built with React + TypeScript + Vite (M5, [ADR-0011](../docs/adr/en/0011-web-ui-and-public-demo.md)). **Zero cost** is the top priority.

| Screen | Public site | Local | Contents |
|---|---|---|---|
| Replay | ✅ | ✅ | Plays an execution trace step by step. A flow diagram (React Flow) colors the boxes passed, rejections and refusals, and shows the source table at that moment. The URL `#replay/<run ID>/<step>` opens a specific moment |
| Evals | ✅ | ✅ | Metrics and per-case results for numeric faithfulness (Wuthering Waves, mortgages) and the injection evals, with a link from each case to its replay |
| Run (local) | — | ✅ | Ask with a scripted demo or real Claude (when an API key is set, within the cost caps) and replay the result right away |

The public site is static files only (no server or LLM runs, so there is no cost and nobody else can use your API).
The replay data is exported by CI in scripted mode (no API key, test calc services); it is not real LLM output.

## Running locally

```bash
# 1. Data (runs every demo and eval in scripted mode and writes JSON)
.venv/bin/python -m servers.web_api.export          # → web/public/data/ (git-ignored)
# 2. Build
(cd web && npm ci && npm run build)                 # → web/dist/
# 3. The local API (127.0.0.1 only). It also serves web/dist, so open it in a browser
.venv/bin/python -m servers.web_api                 # → http://127.0.0.1:8765/
```

During development use `(cd web && npm run dev)` (http://127.0.0.1:5173/, `/api` is proxied to port 8765).
`npm run typecheck` and `npm test` (Vitest) also run in CI.

So that pages on other sites cannot call the local API, it requires `Content-Type: application/json` and checks `Origin`.
Only the fixed demo scripts can be used; arbitrary files cannot be read.

## Publishing to Cloudflare Pages (manual, once)

CI (`.github/workflows/web.yml`) builds on every push to main and publishes when the two secrets below exist. Without them, only publishing is skipped.

1. Create a Cloudflare account at <https://dash.cloudflare.com/sign-up> (free, no credit card).
2. Note your **account ID**: on the right side of the dashboard's "Workers & Pages" screen, or on "Account home" via the account's "…" → "Copy account ID".
3. Create an **API token**: profile at the top right → "My Profile" → "API Tokens" → "Create Token" → "Create Custom Token".
   - Permissions: `Account` · `Cloudflare Pages` · `Edit` (only this one)
   - Account Resources: `Include` · your account
   - Copy the token shown after creation (it is shown only once).
4. Add the secrets to the GitHub repository: "Settings" → "Secrets and variables" → "Actions" → "New repository secret" for
   `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Or with commands:
   ```bash
   gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab     # paste and press Enter
   gh secret set CLOUDFLARE_ACCOUNT_ID -R hexinlong9981/echolab
   ```
5. Run "Actions" → "web" → "Run workflow" (or wait for the next push). The first run creates the project `echolab` before publishing.
   The URL is `https://echolab.pages.dev/` (if the name is taken, Cloudflare assigns another one; check the dashboard).

It stays within the Cloudflare Pages free plan (unlimited bandwidth, up to 500 builds a month; builds run on GitHub Actions, so Cloudflare's builds are not used).
The token can only edit Pages, so a leak cannot change anything else. Revoke it in Cloudflare when it is no longer needed.

## Layout

| Location | Contents |
|---|---|
| `src/replay.ts` | Trace events → replay steps (highlighted boxes, arrows, sources). Pure functions with no React dependency (`replay.test.ts`) |
| `src/FlowDiagram.tsx`, `src/FloatingEdge.tsx` | The flow diagram. Arrows are straight lines between box borders |
| `src/RunPlayer.tsx` | Replay of one run (stepping, autoplay, source table, answer) |
| `src/ReplayView.tsx`, `src/EvalsView.tsx`, `src/LiveView.tsx` | The three screens |
| `../servers/web_api/` | Data export (`export.py`) and the local API (`server.py`). Python standard library only |
