[日本語](../0013-公開のデモサーバ.md) ｜ **English** ｜ [中文](../zh-CN/0013-公开的演示服务器.md)

> This is a translation; the Japanese version is canonical.

# ADR-0013: Public demo server (Hugging Face Spaces, scripted LLM, real calc services)

- Status: Accepted
- Date: 2026-10-04

## Context

The M5 public site is a static replay only, and its records were produced by CI in scripted mode with the **test calc services** ([ADR-0011](0011-web-ui-and-public-demo.md)).
To show interviewers that the calc services really run, a server that runs the real services (the Java calc-engine, OCR, Mushoku Tensei, mortgage) on demand is needed.
The user's policy remains **zero cost**. Publishing real Claude would cost money, so it is out of scope here (the user chose option "A: scripted LLM + real services" first).

## Decision

| Item | Decision |
|---|---|
| Hosting | **Hugging Face Spaces** (Docker, free CPU, no credit card) |
| What runs | `python -m servers.web_api --public`. Only the fixed demos, with the real calc services and the **scripted LLM**. Real Claude (`anthropic`) is always refused; no API key is present |
| Limits | 1 run at a time, up to 3 waiting (503 beyond), per client 6 runs/minute and 60/day (429 beyond), 120 s per run |
| From browsers | CORS only for the public replay site's `Origin`, including preflight (OPTIONS). POSTs from other `Origin`s get 403 |
| Response | A record in the same shape as the static replay (no local absolute paths) plus the elapsed time. Traces go to a per-run temporary directory that is deleted |
| UI | "Run on the server" below a demo's replay. The URL is the build-time `VITE_LIVE_API` (no button without it) |
| Publishing | `.github/workflows/hf-space.yml` sends `deploy/hf/Dockerfile` and only the directories needed at run time to the Space (skipped without the secret `HF_TOKEN` and variable `HF_SPACE`) |

The core does not change (the public mode lives only in `servers/web_api/public.py`).

## Rationale

- Even with the scripted LLM, every calculation is done by the real services, so the demo shows live that "numbers come from tools" (ADR-0001) holds on the real Java and OCR.
- No real Claude means no cost even if third parties use it. The rate limits and single concurrency keep the free CPU from being monopolized.
- Docker packs Java 21, Tesseract and Python into one image, and Hugging Face Spaces runs Docker without a credit card.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Cloudflare Workers | Cannot start child processes (Java, Tesseract) |
| Render free plan | Small memory for Java plus OCR, and it sleeps too |
| Google Cloud Run / Oracle Cloud free tiers | Sign-up requires a credit card |
| Publishing real Claude | Costs money (against the user's policy). If needed, decide separately with a passphrase and a small daily cap |
| Keep the static replay only | Cannot show that the real services run |

## Consequences

- New locations: `servers/web_api/public.py`, `deploy/hf/`, `.dockerignore`, `.github/workflows/hf-space.yml`.
- The free CPU sleeps when unused and starts on the next call (the UI shows "waking the server up"). In local Docker: about 7 s to start, 2.5–10 s per demo (including JVM start-up).
- To publish, the user creates a Hugging Face account, a Space and a write token, and registers `HF_TOKEN`, `HF_SPACE` and `LIVE_API_URL` (`web/README.en.md`).
- Tests: `tests/test_web_api.py` (refusing non-scripted runs, CORS and preflight, rate and queue limits, no paths in responses), `web/src/liveApi.test.ts`.
