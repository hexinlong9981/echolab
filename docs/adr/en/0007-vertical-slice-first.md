[日本語](../0007-縦の切片を優先する.md) ｜ **English** ｜ [中文](../zh-CN/0007-优先纵向切片.md)

> This is a translation; the Japanese version is canonical.

# ADR-0007: Get a minimal end-to-end path working before widening features

- Status: Accepted
- Date: 2026-10-03

## Context

EchoLab consists of several elements: the calculation service, agent orchestration, the gateway, the numeric-trace verifier, evals, image reading, the Web UI and more.
The central mechanism is the numeric-trace verifier, and its effectiveness can only be measured once the whole path works end to end.
We needed to decide in which order to implement the elements.

## Decision

1. **M2 is a vertical slice.** Run "question → gateway → calc-engine → numeric-trace verifier → answer with sources" through a CLI.
   The numeric-faithfulness eval and cost caps (daily and monthly) are also included in M2.
2. **The mortgage pack is added in M3.** At low cost, it shows that "a domain can be added without changing the core" ([ADR-0003](0003-domain-pack-structure.md)).
3. **Directories are created when implemented.** Plans are written in the roadmap in `docs/architecture.md`.

## Rationale

- Getting the end-to-end path working first makes it possible to measure the verifier's effectiveness through evals early. Later feature additions can proceed while watching that metric.
- Including cost caps in the first slice means the LLM-based parts can be operated safely from the start.
- Adding a second domain early lets CI continuously check that the core is domain-agnostic.
- The repository structure matches the implementation, and the roadmap is kept in one place, `docs/architecture.md`.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Build out each element horizontally and integrate at the end | The verifier's effectiveness could only be measured late, delaying input for design decisions |

## Consequences

- The roadmaps in `README.md`, `README.en.md` and `docs/architecture.md` follow this order (M1 to M5).
- Evals (numeric faithfulness) are measured from M2, and the eval pipeline is integrated into CI in M4.
