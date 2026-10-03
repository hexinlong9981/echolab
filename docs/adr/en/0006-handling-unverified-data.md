[日本語](../0006-未確認データの扱い.md) ｜ **English** ｜ [中文](../zh-CN/0006-未确认数据的处理.md)

> This is a translation; the Japanese version is canonical.

# ADR-0006: Unverified data may be used, but answers must always disclose it

- Status: Accepted
- Date: 2026-10-03

## Context

For "numbers you can trust", the formulas must be correct, and so must the data fed into them (multipliers, probabilities, weights).
All current data in `domains/wuwa/data` is unverified sample data (`verified: false`), and no verification procedure had been defined.

## Decision

1. **Enforce the conditions for verified data in the format.** To set `verified: true`, the following three fields are required (checked by JSON Schema).
   - `source`: URL of the source (`https://`)
   - `checked_at`: date of verification (`YYYY-MM-DD`)
   - `game_version`: game version that was checked (e.g. `2.3`)
   When `verified: false`, `source` is required to start with `TODO`.
2. **Unverified data may also be used in calculations.** However, tool results carry `unverified_inputs` (a list of IDs of the unverified data used),
   and the numeric-trace verifier ([ADR-0005](0005-numeric-trace-verifier.md)) sends back any answer citing them that lacks a note stating it is "based on unverified data".
3. **When the game version changes**, the data is copied into a directory for the new version (`data/v<version>/`) and reset to `verified: false` until it is verified again.
   `data_version` in `domain.yaml` declares which version to use.

## Rationale

- An approach that requires verifying all data before use would make neither demos nor development possible. Making the note mandatory lets users judge how reliable the numbers are.
- Enforcing the conditions for verified data in the schema keeps "verified: true without a source" from slipping through review.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Reject unverified data at the gateway | All current data is unverified, so nothing could be answered |
| Only write a caution in the documentation | It would not reach users reading the answers |

## Consequences

- `checked_at` and `game_version` were added to the data schema (`domains/*/data/*/schema/`) and made mandatory when `verified: true`.
- In M2, `unverified_inputs` is added to calc-engine's exposure layer.
