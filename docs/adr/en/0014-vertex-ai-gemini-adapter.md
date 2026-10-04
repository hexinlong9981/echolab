[日本語](../0014-Vertex-AIのGemini適応層.md) ｜ **English** ｜ [中文](../zh-CN/0014-Vertex-AI的Gemini适配层.md)

# ADR-0014: Vertex AI Gemini Adapter (Real LLM Evaluation and Leveraging GCP Free Credits)

- Status: Accepted
- Date: 2026-10-04

## Context

The real LLM evaluation implemented in M2 ([ADR-0008](0008-m2-components-and-contracts.md)) targeted only Claude (Anthropic API). However, the Anthropic API is pay-as-you-go and requires an upfront credit card deposit.
Meanwhile, the project has active Google Cloud free trial credits (approx. 47,000 JPY), and using the Gemini API on Vertex AI enables real LLM evaluations with zero out-of-pocket expenses.
Furthermore, verifying our core invariants (ADR-0008: the LLM never writes numbers and only cites deterministic tool outputs) across different LLM architectures is valuable for future multi-provider readiness.

## Decision

| Item | Decision |
|---|---|
| Library | Use the unified SDK `google-genai` (v2) in Vertex AI mode (`vertexai=True`). |
| Authentication | Google Cloud standard Application Default Credentials (ADC) and environment variables (`GCP_PROJECT_ID`, `GCP_REGION`). |
| Model | Default to `gemini-2.5-flash` (ultra-low cost, fast, accurate function calling). `gemini-2.5-pro` can also be specified. |
| Automatic Function Calling | Disable automatic calling (`disable=True`), ensuring the Agent loop centrally manages tool authorization, execution, and draft rejection. |
| Thinking Blocks | Exclude Gemini 2.5's internal reasoning (`thought=True`) from answer text (`texts`) so the verifier does not misjudge intermediate numbers. Preserve thinking blocks and thought signatures in the conversation history (`raw_content`). |
| Pricing | Register Gemini model rates (input, output, cache) in `config/budget.yaml`, monitored by `Budget` daily and monthly caps. |
| CLI / Evals | Add `--llm gemini` and `--model` options to both `core.agent` and `core.evals`. |

Domain pack isolation (leaving `domains/` untouched) is maintained by implementing this independently in `core/agent/llm/gemini.py`.

## Rationale

- `gemini-2.5-flash` is exceptionally affordable ($0.075 / 1M input tokens, $0.30 / 1M output tokens). Running all 8 faithfulness cases costs only ~$0.003 (less than 0.5 JPY), making frequent evaluation well within GCP trial credits.
- Gemini 2.5 performs internal thinking. If reasoning numbers were exposed in text parts, ADR-0008's numeric verifier would reject drafts due to "unsourced numbers". Filtering out thoughts from answer texts leverages reasoning capabilities while preserving deterministic citation invariants.
- Using `client.aio` from `google-genai` integrates cleanly into `loop.py` without subprocess overhead.

## Rejected Alternatives

| Alternative | Reason for Rejection |
|---|---|
| Claude (Anthropic API) only | Cannot use GCP trial credits; requires out-of-pocket API prepayments (violates the user's cost-first policy). |
| Google AI Studio (API key mode) | Cannot use Vertex AI GCP trial credits and requires separate API key management. |
| Enabling Automatic Function Calling (AFC) | The SDK would execute tools directly, bypassing gateway default-deny, schema checks, source ID generation, and verifier send-backs (violates ADR-0008). |
| Disabling thinking (`budget=0`) | Might reduce tool selection and comprehension accuracy. Letting the model think while excluding thoughts from verification is safer. |

## Consequences

- New files: `core/agent/llm/gemini.py`, `tests/core/test_llm_gemini.py`, `evals/reports/gemini-baseline.md`.
- Changes: `requirements.txt` (added `google-genai`), `config/budget.yaml` (pricing table), `core/agent/` and `core/evals/` (CLI choices).
- Verification: Validated live with `python -m core.evals --llm gemini`, confirming 1.000 faithfulness and seamless tool integration.
