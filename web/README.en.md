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

## Publishing to Cloudflare

Live: **<https://echolab-web.echolab-web.workers.dev/>**

Cloudflare has been merged into Workers, so `web/dist` is published as Workers **static assets** (`web/wrangler.jsonc`; no Worker code, within the free plan).
CI (`.github/workflows/web.yml`) builds on every push to main and publishes with `wrangler deploy` when the two secrets below exist. Without them, only publishing is skipped.

| Secret | Status / how to create |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Registered. The account ID is in the dashboard URL (`https://dash.cloudflare.com/<32 hex characters>/…`) or shown by `npx wrangler whoami` |
| `CLOUDFLARE_API_TOKEN` | <https://dash.cloudflare.com/profile/api-tokens> → "Create Token" → template "Edit Cloudflare Workers" → "Use template" → "Continue to summary" → "Create Token". Register the token shown (only once) with `gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab` |

To publish from your machine (no API token needed after `npx wrangler login`):

```bash
.venv/bin/python -m servers.web_api.export && (cd web && npm run build && npx wrangler@4 deploy)
```

Requests to static assets are free on the Workers free plan. Builds run on GitHub Actions, so Cloudflare's builds are not used.
Revoke the token in Cloudflare when it is no longer needed.

## Layout

| Location | Contents |
|---|---|
| `src/replay.ts` | Trace events → replay steps (highlighted boxes, arrows, sources). Pure functions with no React dependency (`replay.test.ts`) |
| `src/FlowDiagram.tsx`, `src/FloatingEdge.tsx` | The flow diagram. Arrows are straight lines between box borders |
| `src/RunPlayer.tsx` | Replay of one run (stepping, autoplay, source table, answer) |
| `src/ReplayView.tsx`, `src/EvalsView.tsx`, `src/LiveView.tsx` | The three screens |
| `../servers/web_api/` | Data export (`export.py`) and the local API (`server.py`). Python standard library only |
