[日本語](../0005-数値トレース検証器.md) ｜ **English** ｜ [中文](../zh-CN/0005-数值追踪验证器.md)

> This is a translation; the Japanese version is canonical.

# ADR-0005: Numeric-trace verifier policy (derived values are computed by tools)

- Status: Accepted (implemented in M2)
- Date: 2026-10-03

## Context

[ADR-0001](0001-numbers-only-from-tools.md) decided that "numbers in an answer are sent back unless they come from tool results", but did not define the matching rules.
Real answers contain numbers that no tool output directly.

| Kind | Example | Problem |
|---|---|---|
| Different notation | `0.6` → 「60%」, `6192.0` → 「約 6,200」 ("about 6,200") | The strings do not match |
| Derived values | 「A は B より 12% 高い」 ("A is 12% higher than B"), 「差は 740」 ("the difference is 740") | The LLM is computing on its own (violates ADR-0001) |
| Quoting inputs | 「攻撃力 2000 の場合」 ("with 2000 ATK") | Not tool output but user input |

## Decision

1. **Derived values are also computed by tools.** Differences, ratios, % increases and rankings are computed by deterministic compare tools (`compare.diff`, `compare.ratio` and so on,
   domain-agnostic and placed in `core`). The LLM does not even do basic arithmetic.
2. **Numbers are treated as "values with sources".** Each number in a tool result is given an ID (`<call ID>.<field>`),
   and answers are composed by citing those IDs. The verifier checks that each number in an answer falls into one of the following:
   - a value from a tool result (with a source ID)
   - a quotation of a user input value (explicitly given as input)
   - a digit inside a non-numeric expression such as a unit or count (e.g. "3 ways"; managed by an allowlist)
3. **Notation normalization.** Before comparison, percent ↔ decimal, thousands separators and full-width digits are normalized.
   Rounding is allowed only when it matches the tool result rounded to the displayed number of digits (「約」, "about", is treated as a declaration of the displayed precision).
4. **Propagate the unverified-data mark** ([ADR-0006](0006-handling-unverified-data.md)). An answer citing values computed from unverified data must carry a note saying so.
5. If even one number falls into none of these, the answer is sent back. When the retry limit is exceeded, the agent falls back to an answer containing no numbers.

## Rationale

- Letting the LLM compute derived values would leave a hole in the guarantee of ADR-0001. Compare tools can be verified with the same contract-test mechanism (golden cases).
- Composing answers by citing source IDs produces fewer false positives and fewer misses than extracting numbers from free text and matching them.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Allow the LLM to do arithmetic and have the verifier recompute and match | The verifier would have to guess the formula, which is complex. It also contradicts the claim "the AI does not compute" |
| Forbid derived values entirely | Typical questions such as "which one is stronger, and by what %?" could not be answered |

## Consequences

- In M2, golden cases for the compare tools (for `core`) are added (`core/golden/`).
- Evals (from M2) include "numeric faithfulness" as a metric. It is defined as "the share of answers returned to the user that contain no unsourced numbers at all", and 1.0 is the pass condition (`core/evals/`).

## Addendum (M2 implementation)

[ADR-0008](0008-m2-components-and-contracts.md) made the answer a template in which the LLM writes no numbers (numbers cite source IDs with placeholders, and the renderer fills them in).
As a result, points 2 and 3 of the decision are realized as follows.

- For values from tool results, the verifier checks that the source ID in each placeholder was issued within this question. Notation and rounding are determined by the renderer's format (number of decimal places, percentage), so no string matching is needed.
- Notation normalization (full-width digits, thousands separators, percent ↔ decimal) is used when matching digits outside placeholders against numbers in the question.
- The retry limit is 2; beyond that, the run finishes with a fixed answer containing no numbers.
