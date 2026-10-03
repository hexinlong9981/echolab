# domains/mortgage — Domain pack #2: example mortgage repayment calculations

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

> This is a translation; the Japanese version is canonical.

> **These are example calculations, not financial advice.** It is a simple model (fixed rate, monthly payments) that returns unrounded theoretical values.
> Check actual repayments and terms with a financial institution. Every answer ends with a note saying so (`answer_note` in `domain.yaml`).

A minimal example showing that a second domain can be added without changing a single line of the core (ADR-0003, [ADR-0009](../../docs/adr/en/0009-mortgage-pack-and-zero-core-diff.md)).

## Tools

| Tool | Input | Result fields |
|---|---|---|
| `mortgage.equal_payment` (level payment) | `principal` (yen), `annual_rate` (decimal, 0.015 = 1.5% a year), `years` | `monthly_payment`, `total_payment`, `total_interest` |
| `mortgage.equal_principal` (level principal) | Same as above | `first_payment`, `last_payment`, `total_payment`, `total_interest` |
| `mortgage.prepayment` (partial prepayment) | Same as above + `after_months` (payments already made), `prepay_amount` (yen), `method` (`shorten_term` or `reduce_payment`) | `balance_before`, `monthly_payment_after`, `remaining_months_after`, `total_interest_before`, `total_interest_after`, `interest_saved`, `months_saved` |

Differences (for example, the interest difference between the two repayment methods) come from the core compare tools `compare.diff` and `compare.ratio`.

## Layout

| Location | Contents |
|---|---|
| `domain.yaml` | The pack manifest. Declares tools, prompts and the answer note. No data |
| `calc/loan.py` | Calculation. `Decimal` (34 significant digits), output to 6 decimals with ROUND_HALF_EVEN. The shorten-term method advances the balance month by month, and the last payment covers only the remaining principal and interest |
| `calc/server.py` | MCP server (stdio). The core gateway starts it as `mortgage-calc` (`python -m domains.mortgage.calc`) from `config/services.yaml` |
| `calc/schemas/` | Input schemas of the tools (JSON Schema). The gateway checks inputs before calling |
| `golden/` | Golden cases. Each tool has a hand-calculated or closed-form case |
| `prompts/system.md` | The domain system prompt (when to use which tool) |
| `examples/compare_methods.yaml` | A scripted demo (no API key) |

## Run it

```bash
.venv/bin/python -m core.agent "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？" \
  --domain mortgage --llm scripted --script domains/mortgage/examples/compare_methods.yaml
.venv/bin/python -m core.evals --cases evals/faithfulness/mortgage.yaml   # scripted evals (5 cases)
.venv/bin/pytest tests/test_mortgage_pack.py                              # implementation, MCP server and eval tests
```

## Not in the model

Rounding to whole yen, daily interest, bonus payments, variable rates and rate changes, fees, taxes (such as the mortgage tax deduction), and group credit life insurance.
