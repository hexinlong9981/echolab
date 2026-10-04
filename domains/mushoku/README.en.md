# domains/mushoku — Domain pack #3: Mushoku Tensei lore assistant (unofficial)

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

> This is a translation; the Japanese version is canonical.

> **An unofficial fan project.** Rights to *Mushoku Tensei: Jobless Reincarnation* belong to the author, publishers, anime producers and other rights holders.
> No original text, dialogue, illustrations or anime images are included; only short self-written summaries and volume/episode numbers.
> **The data was drafted from memory and checked against the original works by the user on 2026-10-04** (`verified: true`; sources are novel volumes and anime episodes). Map travel days are self-made estimates that the user judged reasonable. New data stays `verified: false` until it is checked.

A pack that answers questions about the setting, timeline and travel routes (M6, [ADR-0012](../../docs/adr/en/0012-mushoku-pack-and-spoiler-protection.md)).
Its highlight is **spoiler protection**: the same mechanism as "filter search results by the user's permissions" in business systems, always enforced in the retrieval layer.

## How spoiler protection works

- **The user sets the progress**: `--context progress=novel:5` (up to light-novel volume 5), `--context progress=anime:2-12` (up to anime season 2 episode 12).
  `progress` is a `user_context` entry in `domain.yaml`; the gateway adds it to tool inputs without showing it to the LLM, and refuses it if the LLM sends one.
- **Only the declared medium is used**: no conversion between novel and anime. Items without a note for that medium are never returned (default-deny).
- **Hidden = nonexistent**: unread people, events and places give the same error as items not in the data.
- **Identity spoilers are prevented too**: aliases that reveal an identity (e.g. Fitz) are used only from the volume/episode where it is revealed. Fact tags are limited to what the sentence itself reveals.
- **Limit**: a spoiler sentence without digits that the LLM writes from its own knowledge cannot be stopped structurally (only the prompt forbids it). Ones with digits are stopped by the verifier.

## Tools

| Tool | What it does | Result |
|---|---|---|
| `lore.search` | Finds facts containing all keywords; people and place names also match | `values`: count and each fact's volume (or season/episode); `texts`: fact sentences (no digits) |
| `timeline.age` | A person's age in the year of an event | `age`, `birth_year`, `event_year` (Kōryū calendar) |
| `timeline.span` | Years between two events | `years`, `from_year`, `to_year` |
| `map.route` | Shortest route on the self-made map (visible roads only) | `total_days`, `legs`; the path in `texts` |

## Layout

| Location | Contents |
|---|---|
| `data/draft-1/` | Facts (40), people (18), events (3), places (8) and roads (7). Schemas in `schema/` |
| `service/` | Search, timeline and routes (`lore.py`) and the MCP server (`server.py`, service `mushoku-lore` in `config/services.yaml`) |
| `golden/` | Golden cases (hand-calculated). Reference implementation: `tests/reference/mushoku_reference.py` |
| `prompts/system.md`, `examples/` | Prompt and scripted demo |

```bash
.venv/bin/python -m core.agent "転移事件のとき、ルーデウスは何歳だった？" --domain mushoku \
  --context progress=novel:3 --llm scripted --script domains/mushoku/examples/teleport_age.yaml
.venv/bin/python -m core.evals --cases evals/redteam/spoilers.yaml      # spoiler-leak evals (7 cases)
```

After checking an item against the source, set `verified: true`, put the exact volume/episode in `source` and the check date in `checked_at` (required by the schema).
