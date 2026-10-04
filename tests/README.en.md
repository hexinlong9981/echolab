# tests/ — Cross-repo tests (Python)

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

*This is a translation; the Japanese version is canonical.*

## Contracts and data

| File | Contents |
|---|---|
| `test_golden_schema.py` | Validates the format of the golden cases (`domains/*/golden`, `core/golden`) and the domain data against JSON Schema. Requires the source of every `verified: false` value to be a TODO. Requires each tool to have at least one case whose `derivation` is something other than `reference` (hand calculation or closed form). Confirms, with violating and valid examples, that the `verified: true` source rules (ADR-0006) are enforced |
| `test_golden_reference.py` | Recomputes the expected values of the golden cases with the Python reference implementation (`reference/calc_reference.py`). Compare-tool cases (`core/golden`) are checked against `core.compare`. Together with the Java contract tests, this guarantees that YAML, Java and Python agree |
| `test_domain_manifest.py` | Validates the domain pack manifests (`domains/*/domain.yaml`) against `schemas/domain.schema.json`. Checks that `name` matches the directory name, that `data_dir`, `golden_dir` and `prompts_dir` exist, that every tool used in the golden cases is declared in `tools`, and that there are no duplicate tool names |

## Unit tests for the core (`core/`): `tests/core/`

No API key and no Java are used. The LLM is replaced by a script (`ScriptedLLM`) or a fake SDK client, and the calculation service by a fake.

| File | Contents |
|---|---|
| `fakes.py` | Fake calculation service for tests (`FakeCalcBackend`). Calculates with the reference implementation without starting Java. Also used by the CLI's `--fake-backend` and by the scripted-mode evals |
| `stub_mcp_server.py` | A small stdio MCP server for tests. Returns results in the same shape as calc-engine (`ToolEnvelope` JSON) |
| `test_gateway.py` | Gateway: allowlist (undeclared or unexposed tools are neither shown nor callable), input schema validation (the service is not called on a violation), call ID and source ID assignment (unique even under concurrency), resolution of source IDs for compare tools and propagation of unverified data |
| `test_gateway_budget.py` | Cost ledger and caps: calculation from the price table, daily and monthly caps, UTC day and month boundaries, stopping when the ledger cannot be read, conservative estimates for models missing from the price table, overrides via environment variables |
| `test_mcp_backend.py` | Runs `McpStdioBackend` against `stub_mcp_server.py`: listing and calling tools, reporting startup failures, launching from `config/services.yaml` |
| `test_compare.py` | Compare tools (difference, ratio, % increase): calculation, rounding, division by zero |
| `test_verifier.py` | Renderer formatting (digits, percentages, thousands separators, rounding) and verifier verdicts (placeholder syntax, unknown source IDs, unsourced numbers, quoting numbers from the question, allowlist, notes on unverified data) |
| `test_agent.py` | Agent loop: parallel tool calls, recovery from tool errors, rejection and retry, switching to a number-free answer, cost caps, loop limit, refusals and truncated output, LLM failures |
| `test_llm_anthropic.py` | Claude LLM implementation: request construction (model, thinking effort, fallback, prompt caching), response normalization, billing on fallback, refusals and API errors |
| `test_llm_scripted.py` | Scripted LLM: response order, `expect` matching, loading the example scripts |
| `test_trace.py` | Execution trace: JSONL with one event per line, serialization of contract types, contents of the events the agent records |
| `test_evals.py` | Runs all numeric-faithfulness eval cases in scripted mode and checks that the result matches the committed `evals/reports/scripted-baseline.md` |

## Domain pack #2: mortgages (ADR-0009)

No Java is used. The pack's MCP server (Python) is started as a real child process, so these tests run in the CI `python` job every time.

| File | Contents |
|---|---|
| `reference/mortgage_reference.py` | Reference implementation for mortgages. It calculates in a different way (`float`, the balance formula and a logarithm for the number of months) from the pack's implementation (`Decimal`, advancing the balance month by month) |
| `test_mortgage_pack.py` | The pack's implementation against golden cases, explanations of invalid inputs, the real MCP server started through the gateway (golden cases and errors), the Agent round trip and the answer note, scripted evals (`evals/faithfulness/mortgage.yaml`) and their baseline |
| `test_pack_isolation.py` | Checks the rules of the CI check "pack changes do not change the core" (`.github/scripts/check_pack_isolation.py`) in temporary git repositories |

## Screenshot reading and injection evals (ADR-0010)

| File | Contents |
|---|---|
| `test_vision.py` | `servers/vision_mcp`: extraction with templates (tested on the recorded OCR output `.ocr.txt`), instructions written in images never appear in results, out-of-range and duplicate errors, image path restrictions (outside the roots, symbolic links, file types), the real Tesseract and MCP server, the template schema (`schemas/vision_template.schema.json`) |
| `test_redteam.py` | Runs the injection evals (`evals/redteam/cases.yaml`) in scripted mode: no attack succeeds, image text never appears in tool results, and the baseline |

The real-OCR tests need Tesseract (with Japanese data). They are skipped without it (in CI, `ECHOLAB_OCR_REQUIRED=1` makes them fail instead of skipping).

## End-to-end tests: `tests/e2e/`

`test_mcp_e2e.py` starts the real calc-engine (the MCP server jar) as configured in `config/services.yaml`.

- Checks every golden case through MCP (the third check, after the Java unit tests and the Python reference implementation).
- Verifies parallel calls right after startup, errors for invalid input, and propagation and notes of unverified data when data is referenced.
- Runs the agent loop with the scripted LLM on top of the real calculation service.

The jar and JDK 21 are required. If either is missing, the tests are skipped (in CI, `ECHOLAB_E2E_REQUIRED=1` makes them fail instead of being skipped).

```bash
(cd services/calc-engine && ./gradlew bootJar)      # build/libs/calc-engine-mcp.jar
export JAVA_HOME=/path/to/jdk-21 PATH="$JAVA_HOME/bin:$PATH"
.venv/bin/pytest -m e2e
```

In CI, the `python` job in `test.yml` runs `pytest -m "not e2e"`, and the `e2e` job builds the jar and then runs `pytest -m e2e`.

The `pack-isolation` job checks in the git history that domain pack changes do not change the core (ADR-0009).
