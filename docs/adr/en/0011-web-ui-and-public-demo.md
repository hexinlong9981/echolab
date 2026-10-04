[日本語](../0011-Web-UIと公開の方針.md) ｜ **English** ｜ [中文](../zh-CN/0011-网页界面与公开方针.md)

> This is a translation; the Japanese version is canonical.

# ADR-0011: Web UI and public demo policy (zero cost)

- Status: Accepted
- Date: 2026-10-04

## Context

M5 covers chat, replay of execution traces, an eval dashboard and a public demo ([ADR-0007](0007-vertical-slice-first.md)).
Answers need an LLM (paid), the Java calc service and OCR, so a public demo where anyone can ask live would need an always-on server and API spending.
The user's policy is **cost first, ideally completely free**.

## Decision

Based on the user's decisions (2026-10-04).

| Item | Decision |
|---|---|
| What is public | **Only a static replay and eval dashboard.** No server or LLM runs |
| Live screen | **Local only** (`python -m servers.web_api`, `127.0.0.1`). Used over screen sharing in interviews. Real Claude follows the core cost caps |
| Hosting | **Cloudflare Pages** (free plan) |
| UI technology | **React + TypeScript + Vite**, with React Flow for the flow diagram |
| Publishing | **GitHub Actions** publishes with wrangler after data export, type checks, tests and build pass. Without the secrets (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) only publishing is skipped |

- CI exports the replay data in scripted mode (no API key, test calc services) with `python -m servers.web_api.export`. The output is the same every time and contains no local absolute paths. The screen states that these are scripted-mode records.
- The local API uses only the Python standard library (no new dependencies). So that pages on other sites cannot call it and spend money, it requires `Content-Type: application/json` and checks `Origin`. Only the fixed demo scripts can be used.
- UI text is in Japanese (the same as the CLI and evals).

## Rationale

- With a real LLM behind a public demo, even with cost caps, third-party use would hit the caps and stop the demo. A static replay has neither cost nor risk.
- The project's highlights (the source table, rejections, refusals) come across better step by step in a replay than in a live answer.
- With the local screen, an interviewer's "ask something else" can be answered on the spot (when an API key is available).
- Building in CI before publishing keeps the published data consistent with that commit's tests and evals.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Public live demo (server + real Claude) | Server and API costs, spending by third parties. No hosting that stays free |
| Public live demo (server + scripted LLM) | The script does not read the question, so free questions cannot be answered. It shows the same as the static replay but needs a server |
| GitHub Pages | Free and already in use, but the user chose Cloudflare Pages as originally planned |
| Building on Cloudflare (repository integration) | Exporting the data needs Python, and it could publish before the tests run |
| FastAPI for the local API | Adds dependencies; the standard library is enough |

## Consequences

- New locations: `web/`, `servers/web_api/`, `.github/workflows/web.yml`.
- To publish, the user must create a Cloudflare account and register two secrets (steps in `web/README.en.md`).
- The public replay contains scripted-mode records only. Whether to publish real-LLM records will be decided when real evals are run.
- Tests: `tests/test_web_api.py` (export and API checks), `web/src/replay.test.ts` (building replay steps, Vitest).
