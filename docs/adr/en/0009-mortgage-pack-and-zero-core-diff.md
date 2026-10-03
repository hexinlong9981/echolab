[日本語](../0009-住宅ローンのパックとコアの差分ゼロ.md) ｜ **English** ｜ [中文](../zh-CN/0009-房贷领域包与核心零改动.md)

> This is a translation; the Japanese version is canonical.

# ADR-0009: The mortgage pack and the "zero core diff" check

- Status: Accepted
- Date: 2026-10-04

## Context

[ADR-0003](0003-domain-pack-structure.md) decided to prove that the core does not depend on any domain with a second pack (mortgage, M3),
and to check in CI that "the change that adds the pack has zero diff in the core".
When the M2 core was used for the mortgage pack, three things were missing.

| Point | M2 core | Problem |
|---|---|---|
| Python tool services | The `command` in `config/services.yaml` is looked up on PATH | It cannot start where PATH has no `python` (Linux with only `python3`). Even if it starts, an interpreter outside the virtual environment lacks the dependency (`mcp`) |
| Eval domain | Evals always run with the `wuwa` pack | Mortgage eval cases cannot run |
| Answer note | Only the unverified-data note | The only way to always add a "not financial advice" note is to ask in the prompt |

## Decision

### Extend the core first, in a domain-agnostic way (separate commit)

Separately from the commit that adds the pack, these changes went into the core (commit `7fb32cd`). None of them knows about mortgages.

- `python` in `command` starts the interpreter that is running now (`sys.executable`), the same idea as `JAVA_HOME` for `java`.
- An eval case file names its pack with a top-level `domain` (default `wuwa`). The report shows the domain.
- `answer_note` in `domain.yaml`: a note that the Agent deterministically appends to answers that passed verification. It is added after verification, so it must not contain digits (checked by the schema). Evals check it with `expect.answer_note`.
- `data_dir` and `data_version` in `domain.yaml` are optional (packs without data).

### Pack layout

| Location | Contents |
|---|---|
| `domains/mortgage/domain.yaml` | Three tools (`mortgage.equal_payment`, `mortgage.equal_principal`, `mortgage.prepayment`) and `answer_note` |
| `domains/mortgage/calc/` | Calculation (`loan.py`, `Decimal`, 34 significant digits, output to 6 decimals with ROUND_HALF_EVEN) and the MCP server (`server.py`, stdio). Results are the same `ToolEnvelope` JSON as calc-engine |
| `domains/mortgage/golden/` | Golden cases (each tool has at least one hand-calculated or closed-form case) |
| `domains/mortgage/prompts/system.md` | When to use which tool. No numbers or typical interest rates |
| `config/services.yaml` | `mortgage-calc`: `python -m domains.mortgage.calc` |

- The calc service lives inside the pack. It is not a separate service like calc-engine (Java); the pack is a minimal, self-contained example.
- Two independent implementations are checked against each other: the pack's (`Decimal`, advancing the balance month by month) and `tests/reference/mortgage_reference.py` (`float`, balance formula and a logarithm for the number of months).
- The model is simple (fixed rate, monthly payments, unrounded theoretical values) and **is not financial advice**. Every answer carries a note saying so, through `answer_note`.

### The "zero core diff" check

The `pack-isolation` CI job (`.github/scripts/check_pack_isolation.py`) checks two things in the git history.

1. None of the commits added by a push or pull request changes both `domains/` and `core/`.
2. The commit that added each pack's `domain.yaml` did not change `core/` (except the first pack, `wuwa`, which was created together with the core).

## Rationale

- "We added the pack and fixed the core a little" would not prove the claim of ADR-0003 (the core is domain-agnostic).
  Missing pieces were added to the core as domain-agnostic features in a separate change, so both changes can be checked.
- The Agent appends `answer_note` for the same reason as ADR-0001 (guarantee what matters by structure). A request in the prompt cannot be verified.
- Writing the two implementations in different ways lowers the chance that both share the same mistake (for example, the last payment in the shorten-term method).

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Write `.venv/bin/python` in `config/services.yaml` | The virtual environment's location differs per machine, and CI (`setup-python`) has no `.venv` |
| Ask for the note in the prompt | Omissions cannot be verified; only real-LLM evals would show them |
| Add mortgage calculations to calc-engine (Java) | It changes code outside the pack, so it does not show that a pack alone is enough |
| Apply rule 1 to every commit in history | The M2 commit (which created `domain.yaml` and `core/` together) would violate it. The rule applies to changes from now on |

## Consequences

- Adding a pack: add `domains/<name>/` and an entry in `config/services.yaml`, tests (`tests/`) and eval cases (`evals/faithfulness/<name>.yaml`). `core/` does not change.
- When the core must change, do it in a separate, domain-agnostic commit (`pack-isolation` stops mixed commits).
- Tests: `tests/test_mortgage_pack.py` (implementation vs golden cases, starting the MCP server, the Agent, evals), `tests/test_golden_reference.py` (reference implementation), `tests/test_pack_isolation.py` (the check's rules).
