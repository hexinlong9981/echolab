[日本語](../0012-無職転生のパックとネタバレ防止.md) ｜ **English** ｜ [中文](../zh-CN/0012-无职转生领域包与防剧透.md)

> This is a translation; the Japanese version is canonical.

# ADR-0012: The Mushoku Tensei pack and spoiler protection

- Status: Accepted
- Date: 2026-10-04

## Context

The third domain pack is a lore assistant for *Mushoku Tensei* (M6). Unlike Wuthering Waves (numeric optimization) and mortgages (example calculations),
its subject is "reasoning over knowledge and time", and its highlight is **spoiler protection**. This has the same structure as
"filter search results by the user's permissions" (permission-aware RAG) in business systems. The user's decisions (2026-10-04): scope covers search, timeline and routes;
data covers all light-novel volumes and the anime, drafted from memory and marked unverified; retrieval is a structured, deterministic lookup (no embeddings).

## Decision

### The user sets the progress, and the retrieval layer always filters by it

- The progress `progress` (`novel:<volume>` or `anime:<season>-<episode>`) is set by the **user** (CLI `--context progress=…`, `context` in eval cases).
- The core gained a generic `user_context` (`domain.yaml`) in a separate commit. The gateway removes declared items from the schemas shown to the LLM,
  refuses them if the LLM sends them regardless of the service schema, and adds the user's value to the input. The LLM cannot widen the progress.
- The service filters only by the declared medium's note and does not convert between media. Items without a note are never returned (default-deny).
- Hidden items give the same error as nonexistent ones (so existence itself does not leak).
- Aliases that reveal an identity (`secret_aliases`) are used only from the volume/episode of the reveal. Fact tags are limited to what the sentence itself reveals
  (so that unrevealed relationships cannot be matched through tags or aliases). These data rules are checked by tests.

### Separate fact sentences from numbers

- The core gained a generic `texts` (non-numeric sentences) in a separate commit. Fact sentences are returned in `texts` and do not become source IDs.
- Fact sentences contain no digits (checked by the schema). Years, ages, days, volumes and episodes are returned in `values` and cited with placeholders (ADR-0001).

### Data and rights

- The data (40 facts, 18 people, 3 events, 8 places, 7 roads) is a draft written from memory, all `verified: false` with `source: TODO…`.
  When a volume/episode is uncertain, the **later** one is used (too early would be a spoiler). Anything uncertain is left out.
- Every answer carries an `answer_note` saying it is an unofficial summary based on unverified draft data.
- No original text, dialogue, illustrations or anime images are included; only short self-written summaries and volume/episode numbers. The map is self-made, and days are estimates.

## Rationale

- Leaving progress to the LLM lets questions or injections widen it and leak spoilers. Enforcing it in the gateway and service prevents leaks even if the LLM is fooled.
- Embedding search needs money or a heavy environment and is hard to pin down in tests. Structured lookup is free and deterministic, and filtering can be tested reliably.
- Marking the draft as unverified lets the mechanism be built first without presenting mistakes as facts. Items become `verified: true` as the user checks them.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Pass progress in the prompt and ask the LLM to respect it | Broken by injections or rephrasing; cannot be verified |
| Embedding (vector) search | Needs money or a heavy environment; results are not deterministic and hard to test |
| Converting between novel and anime progress | Their structures differ, and conversion errors become spoilers |
| Allowing digits in fact sentences | Copying them into answers would create unsourced numbers (ADR-0001) |

## Consequences

- New locations: `domains/mushoku/`, `evals/faithfulness/mushoku.yaml`, `evals/redteam/spoilers.yaml`; `mushoku-lore` in `config/services.yaml`.
- Known limit: a spoiler sentence without digits that the LLM writes from its own knowledge cannot be stopped structurally (the prompt forbids it). Ones with digits are stopped by the verifier.
- Tests: `tests/test_mushoku_pack.py`, `tests/core/test_user_context.py`, `tests/test_golden_reference.py` (reference implementation `tests/reference/mushoku_reference.py`).

## Addendum (2026-10-04): data review

The author checked the 79 items drafted by Claude (40 facts, 18 people, 3 events, 8 places, 7 roads and others) one by one against the original works.
35 items were confirmed as-is and 44 were corrected; all are now `verified: true` (sources such as "novel vol. X" and "anime season X episode X").
Most corrections were anime episode numbers, including spoiler-gating boundaries (for example, the episode where Fitz's identity is revealed).
The unverified note is now added only to answers that use unverified data. Data added later stays `verified: false` until checked.
The known limit that spoiler sentences without digits cannot be stopped structurally is unchanged.
