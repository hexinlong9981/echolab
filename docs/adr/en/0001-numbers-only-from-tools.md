[日本語](../0001-数値はツールからのみ.md) ｜ **English** ｜ [中文](../zh-CN/0001-数值仅来自工具.md)

> This is a translation; the Japanese version is canonical.

# ADR-0001: Numbers in answers come only from the results of deterministic tools

- Status: Accepted
- Date: 2026-10-03

## Context

LLMs can produce plausible-looking numbers. In build advice, "a single wrong number is enough to lose trust",
so "usually right" is not good enough.

## Decision

- All numbers such as damage, scores and probabilities are computed deterministically by calculation services (`services/calc-engine` and others).
- The LLM's role is limited to understanding the question, choosing tools and explaining the results.
- For each number in an answer, the numeric-trace verifier (`core/verifier`, M2) checks which tool result it comes from, and sends the answer back if there is no match.
- Calculation results are returned with a breakdown (such as the value of each multiplier zone) and serve as the sources for the answer.

## Rationale

- Deterministic calculation can be tested, reproduced and version-controlled.
- Checking the golden cases in both Java and Python also catches implementation errors.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Let the LLM compute, asking for accuracy in the prompt | Correctness cannot be guaranteed, and there is no way to detect errors |
| Let the LLM write and run code | The code differs every time and cannot be tested or version-controlled |

## Consequences

- The calculation service's tests (property tests, contract tests) become the foundation of answer correctness.
- In M1, the calculation service prepares for this decision by returning results with a breakdown. The checking is done by the numeric-trace verifier in M2.
