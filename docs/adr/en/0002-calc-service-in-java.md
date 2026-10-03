[日本語](../0002-計算サービスはJava.md) ｜ **English** ｜ [中文](../zh-CN/0002-计算服务使用Java.md)

> This is a translation; the Japanese version is canonical.

# ADR-0002: Implement the calculation service in Java 21

- Status: Accepted
- Date: 2026-10-03

## Context

Python has a rich ecosystem for agents, retrieval and evaluation. The calculation service, however, has different requirements:
"it must not be wrong" and "it must run large numbers of trials fast".

## Decision

The calculation service for the Wuthering Waves domain (`services/calc-engine`) is implemented in Java 21; everything else (`core/` and so on) is implemented in Python.

## Rationale

1. **Preventing errors with types**: model with `record` and `sealed interface`, so that code does not compile unless a `switch` covers every kind of echo sub-stat. Precision is handled with `BigDecimal`.
2. **Performance**: Monte Carlo simulation can be implemented three ways (sequential, parallel stream, virtual threads) and compared with JMH.
3. **MCP is language-independent**: writing the tool in Java does not change the agent side. This demonstrates the separation between tools and the agent in practice.
4. **Contract tests**: the same golden cases are checked in both Java and Python, guaranteeing agreement across languages.
5. **Startup speed**: as a future option, GraalVM Native Image can speed up resuming from auto-stop on platforms such as Fly.io.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| All Python | Simplest, but loses type-based exhaustiveness guarantees and the demonstration of cross-language contract tests |
| All Java (orchestration with Spring AI as well) | Fewer AI and evaluation tools than Python; the orchestration part would have to be rebuilt |

## Consequences

- CI has two pipelines: Java (`java.yml`) and Python (`test.yml`).
- The golden case format (`tests/schemas/golden.schema.json`) becomes the contract between the two languages.
