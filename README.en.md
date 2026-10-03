# EchoLab

> **An AI assistant that never lets the AI do the math.** Numbers come only from deterministic tools; the LLM understands and explains.
> A **non-official, non-commercial fan project** themed on *Wuthering Waves*. The main README is in [Japanese](README.md).

## Why

LLMs can produce plausible but wrong numbers. EchoLab answers "can I trust this number?" by design:

- **Numbers from tools only** — damage, scores and probabilities are computed by `services/calc-engine` (Java 21) with a full breakdown used as citations. The LLM does no arithmetic at all: differences, ratios and % increases come from domain-agnostic `compare.*` tools. A numeric-trace verifier (M2, ADR-0005) checks every number in an answer against tool-result source IDs or quoted user input, and rejects the answer otherwise.
- **Unverified data is flagged** — sample data may be used, but answers built on it must say so; `verified: true` requires an https source, check date and game version, enforced by JSON Schema (ADR-0006).
- **Cross-language contract tests** — the same golden cases (`domains/wuwa/golden/*.yaml`, each recording its `derivation`) are checked by the Java implementation and an independent Python reference implementation. `domain.yaml` is schema-checked too.
- **Default-deny gateway, cost caps, evals** — gateway with daily/monthly cost caps and numeric-faithfulness eval in M2; prompt-injection redteam and CI eval pipeline in M4.
- **Domain packs** — a domain-agnostic core (ADR-0003). The second pack, a minimal mortgage calculator (M3), proves that a new domain can be added without changing the core.

## Status: M1

Java 21 calc-engine (records, sealed interfaces, `BigDecimal`), exact Markov-chain gacha solver plus Monte Carlo (sequential / parallel stream / virtual threads, benchmarked with JMH), jqwik property tests, ArchUnit rules, Error Prone with `-Werror`, JaCoCo ≥ 90% line coverage, GitHub Actions CI.

## Roadmap

Build a thin end-to-end slice before widening (ADR-0007). Details: [docs/architecture.md](docs/architecture.md).

| Milestone | Scope | Status |
|---|---|---|
| M1 | Java calc-engine, golden cases, CI | Done |
| M2 | Vertical slice via CLI: question → gateway (allowlist, schema, cost caps) → calc-engine as MCP → numeric-trace verifier + compare tools → cited answer; numeric-faithfulness eval, execution trace | Planned |
| M3 | Mortgage domain pack (minimal); CI check that the core diff is zero | Planned |
| M4 | Screenshot reading, prompt-injection redteam set, eval pipeline in CI | Planned |
| M5 | Web UI, trace replay, eval dashboard, public demo | Planned |

## Layout

```
domains/wuwa/  Domain pack #1: Wuthering Waves (domain.yaml, golden cases, sample data)
services/      calc-engine (Java 21)
tests/         Cross-repo tests (schema checks, Python reference implementation)
docs/          Architecture and ADRs (Japanese)
```

Only implemented parts live in the repo; future directories are created when implemented.

## Quick start

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check
cd ../.. && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest
```

## Disclaimer

Sample values in `domains/*/data` are unverified (`verified: false`) and not official. The planned mortgage pack is an example calculation, not financial advice. All rights to the games and works belong to their respective owners. See [DISCLAIMER.md](DISCLAIMER.md). Code is MIT-licensed.
