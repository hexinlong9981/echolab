[日本語](../0008-M2の構成と契約.md) ｜ **English** ｜ [中文](../zh-CN/0008-M2的结构与契约.md)

> This is a translation; the Japanese version is canonical.

# ADR-0008: M2 components and contracts between them

- Status: Accepted
- Date: 2026-10-03

## Context

M2 runs "question → gateway → calc-engine → numeric-trace verifier → answer with sources" through a CLI ([ADR-0007](0007-vertical-slice-first.md)).
Because the Java calculation service and the Python core are built in parallel, the shape of the boundaries has to be decided first.

## Decision

### Overall

| Component | Location | Role |
|---|---|---|
| Contracts | `core/contracts.py` | Shapes of the data passed between components |
| Gateway | `core/gateway/` | Allowlist (`domain.yaml`, default deny), input schema validation, assignment of call IDs and source IDs, cost caps |
| Compare tools | `core/compare/` | Difference, ratio, % increase ([ADR-0005](0005-numeric-trace-verifier.md)). Inputs are source IDs |
| Verifier and renderer | `core/verifier/` | Checking answer templates and replacing placeholders |
| Agent and CLI | `core/agent/` | Tool-calling loop with Claude, send-backs, CLI |
| Execution trace | `core/trace/` | Records one question to one JSONL file (`.echolab/traces/<run_id>.jsonl`) |
| Evals | `core/evals/`, `evals/` | Numeric faithfulness |
| MCP server | `services/calc-engine` (`dev.echolab.app`) | Spring Boot + Spring AI MCP server (stdio). Only calls the public API of `calc` ([ADR-0004](0004-no-spring-in-m1.md)) |

### The LLM does not write numbers

- The LLM's final answer is a **template**, and numbers are always cited with placeholders `[[c1.total]]` (with a format: `[[c1.total|0]]`, `[[c2.ratio|%1]]`).
- Replacement with numbers is done by a deterministic renderer. Since there is no path for the LLM to copy digits, transcription errors and rounding mismatches cannot occur.
- The verifier checks that every digit in the template outside placeholders (full-width digits normalized with NFKC) is either a quotation of a number in the user's question or on the allowlist (such as list item numbers).
  If it is neither, the answer is sent back.
- If any cited value derives from unverified data, the renderer adds a note automatically ([ADR-0006](0006-handling-unverified-data.md)).

### Tool names and results

- Domain tool names (`damage.expected`) are exposed over MCP and to the LLM with `.` replaced by `_` (`damage_expected`), because Claude API tool names cannot contain `.`.
- The shape of a tool's input is the same as the `input` of its golden cases. Inputs that reference data (`banner` for `gacha.probability_within`, `profile` for `echo.score`) are also accepted.
- The result is a single JSON object: `{"tool", "values": {field: decimal string}, "unverified_inputs": [...], "data_version"}`.
- Source IDs (`<call ID>.<field>`) are assigned by the gateway. The calculation service does not know the IDs.

### LLM and cost

- The model is Claude Opus 5.5 (`claude-opus-5-5`). It sits behind an abstraction layer, and tests and CI use a fake LLM that responds according to a script.
- Cost caps are 1 USD per day and 10 USD per month (configurable). When a cap is reached, the run ends without calling the LLM.
- Evals with the real LLM are run manually on a local machine, and only the aggregated results are committed. CI holds no API key.

## Rationale

- The placeholder approach guarantees "the LLM does not compute" from ADR-0005 by structure rather than by prompt instructions.
- Fixing the boundaries with JSON and a Protocol makes it possible to build Java and Python in parallel and to test each in isolation by substituting fakes.

## Rejected alternatives

| Alternative | Reason for rejection |
|---|---|
| Let the LLM write numbers directly, and have the verifier extract them from free text and match | Judging notation variants, rounding and thousands separators is complex, causing both false positives and misses |
| Have the calculation service assign source IDs | Making IDs unique within a single question is the gateway's responsibility. This keeps the service stateless |

## Consequences

- Golden cases are checked not only by Java unit tests and the Python reference implementation, but also by end-to-end tests through MCP.
- The M2 section of `docs/architecture.md` was updated to match this ADR.

## Addendum (details decided during implementation)

- The execution trace records one question to one file (`.echolab/traces/<run ID>.jsonl`).
- The tool service connection (`core/gateway/mcp_backend.py`) sends calls to the same service one at a time and waits up to 30 seconds for each response.
  A timeout is returned to the LLM as a `ToolError` and does not stop the whole question. If `java` is not on PATH, the service is started with `JAVA_HOME/bin/java`.
- Even when a server-side fallback on refusal bills a model that is not in the pricing table, the charge is always recorded in the ledger. The amount is estimated at the highest rate in the pricing table so that the cap check is not too lenient.
- The end-to-end tests through MCP (`tests/e2e/`) run in CI after the jar is built (the `e2e` job in `test.yml`).
- Known limitations are collected under "Known limitations" in `docs/architecture.md`.
