[日本語](../0004-M1ではSpringを導入しない.md) ｜ **English** ｜ [中文](../zh-CN/0004-M1不引入Spring.md)

> This is a translation; the Japanese version is canonical.

# ADR-0004: Do not introduce Spring in M1; build a plain Java library

- Status: Accepted
- Date: 2026-10-03

## Context

The calculation service will ultimately be exposed as an MCP server (Spring Boot + the Spring AI MCP Server).
However, the goal of M1 is to establish that "the calculations are correct".

## Decision

In M1, `calc-engine` is built as a plain library with no dependency on Spring; the layer that exposes it over MCP is added separately in M2.

## Rationale

1. **Separation of concerns**: separating the calculation logic from the framework makes tests fast and simple (all M1 tests run without starting a Spring context).
2. **Few dependencies**: the only production dependency in M1 is YAML loading (Jackson), which keeps it easy to maintain even with a strict build and static analysis (Error Prone, `-Werror`).
3. **Replaceability**: adding the exposure layer later means that changes in MCP SDK or Spring versions do not affect the calculation logic.
4. **Native Image**: the larger the framework-independent part, the fewer problems with GraalVM Native Image.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Build it as a Spring Boot app from the start | Adds dependencies and configuration not used in M1, making it harder to focus on calculation correctness |

## Consequences

- In M2, an `app` layer (Spring Boot, MCP tool definitions) is added that only calls the public API of `calc`.
- In M2, an ArchUnit rule is added that "the calculation package does not depend on any framework".
