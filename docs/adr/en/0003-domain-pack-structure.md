[日本語](../0003-ドメインパック構成.md) ｜ **English** ｜ [中文](../zh-CN/0003-领域包结构.md)

> This is a translation; the Japanese version is canonical.

# ADR-0003: Separate a domain-agnostic core from domain packs

- Status: Accepted
- Date: 2026-10-03

## Context

The game is the subject matter; what we really want to build is the mechanism for "an AI that cannot get numbers wrong".
We need to actually demonstrate that the mechanism does not depend on a particular domain.

## Decision

- `core/` (orchestration, gateway, numeric verification, evals, tracing) contains no domain concepts at all.
- Domain knowledge lives in `domains/<name>/`, and `domain.yaml` declares tools, data version, golden cases, prompts and filtering policy.
- The gateway allows only the tools declared in `domain.yaml` (default deny).
- Two packs demonstrate this: ① Wuthering Waves (numeric optimization, Java) and ② mortgage (minimal example, Python). The order is set in [ADR-0007](0007-vertical-slice-first.md).
- Packs can be added in the same format, so a third pack and beyond can be added without changing the core.

## Rationale

- CI can check that adding a new domain produces zero diff in `core/` (M3, with the mortgage pack).
- Two packs of different nature (numeric optimization in Java and a minimal example in Python) show that the core depends on neither the domain nor the implementation language.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Build a separate app per domain | Common parts are duplicated, and portability cannot be demonstrated |
| Register plugins in code | A declaration (YAML) is easier to check as the gateway's allowlist |

## Consequences

- The `domain.yaml` format becomes the contract between the core and packs. The schema (`tests/schemas/domain.schema.json`) was added in M1 and is checked by `tests/test_domain_manifest.py`.
