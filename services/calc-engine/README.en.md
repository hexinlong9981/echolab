# calc-engine — Calculation service (Java 21)

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

*This is a translation; the Japanese version is canonical.*

Handles the deterministic calculations for the Wuthering Waves domain. **The LLM uses only values calculated here in its answers** (ADR-0001).

## M1 scope

| Package | Contents |
|---|---|
| `domain` | Models built with `record` and `sealed interface` (substats, echoes, stats). The precision policy is centralized in `Precision` (`BigDecimal`, DECIMAL64) |
| `damage` | Expected damage. Returns the value of each multiplier as a breakdown (used for numeric tracing of answers) |
| `echo` | Weighted score of echo substats. Exhaustive handling of sealed types with `switch` |
| `gacha` | Pity model. Exact solution (Markov chain) and Monte Carlo (sequential, parallel stream, virtual threads) |
| `golden` | Loading of golden cases (`domains/wuwa/golden/*.yaml`) |

In M1 this was built as a pure library without a Spring dependency, to pin down the correctness of the calculations first (ADR-0004). This policy is unchanged in M2: ArchUnit keeps `dev.echolab.calc` framework-independent.

## M2: MCP server (`dev.echolab.app`)

The public layer called over MCP stdio from the Python core (the gateway) (ADR-0008).
It runs as a Spring Boot 4.1 + Spring AI 2.0 MCP server (`spring-ai-starter-mcp-server`, synchronous, stdio). It only calls the public API of `calc` and contains no formulas itself.

| Package | Contents |
|---|---|
| `app` | Application class, tool registration (`McpToolConfiguration`), conversion to MCP (`McpToolAdapter`) |
| `app.tool` | Implementation of the four tools: input validation (with Japanese messages) and result JSON. Depends on neither Spring nor the MCP SDK |
| `app.data` | Loading of `domains/wuwa` data (gacha rules, echo weights) |

### Tools

The MCP name is the domain tool name with `.` replaced by `_` (because `.` is not allowed in Claude API tool names).
The input shape is the same as the `input` of the golden cases (`domains/wuwa/golden/*.yaml`), so golden case inputs can be passed as is.

| MCP name | Domain tool name | Result `values` |
|---|---|---|
| `damage_expected` | `damage.expected` | `base`, `bonus_multiplier`, `crit_multiplier`, `defense_multiplier`, `resistance_multiplier`, `total` |
| `echo_score` | `echo.score` | `score`, `percent_of_ideal` |
| `gacha_probability_within` | `gacha.probability_within` | `probability` (exact solution) |
| `gacha_simulate` | `gacha.simulate` | `probability`, `std_error` (Monte Carlo; `trials` 1 to 1,000,000, `seed`, `method` = `sequential` / `parallel_stream` / `virtual_threads`) |

The input schemas (describing the meaning, unit and range of each field in Japanese) are in `src/main/resources/tools/*.schema.json`.

### Data references

Instead of passing values directly, a data ID can be specified. Exactly one of the two must be given (both or neither is an error).

| Tool | Direct value | Data reference |
|---|---|---|
| `gacha_probability_within`, `gacha_simulate` | `rules` | `banner` (`banners[].id` in `gacha_rules.yaml`) |
| `echo_score` | `weights` | `profile` (`profiles[].id` in `echo_weights.yaml`) |

If `max_roll` is omitted, `echo_score` uses `max_roll` from `echo_weights.yaml`.

The data location is `$ECHOLAB_DATA_ROOT/wuwa/` + `data_dir` from `domain.yaml` (the environment variable defaults to `domains` relative to the working directory). The version directory name is not hard-coded.

### Results

A single JSON object is returned as text content (`ToolEnvelope` in `core/contracts.py` on the Python side).

```json
{"tool": "gacha.probability_within",
 "values": {"probability": "0.6058637851964593"},
 "unverified_inputs": ["gacha_rules:featured-character"],
 "data_version": "v2.x"}
```

- `values` are decimal strings. `BigDecimal` results are rounded to the output precision of `Precision` (6 decimal places); probabilities (`double`) use the shortest decimal representation.
- `unverified_inputs` are the IDs of unverified data (`verified: false`) used in the calculation (`<data file name>:<item ID>`, e.g. `echo_weights:max_roll`). They are sorted and free of duplicates (ADR-0006).
- `data_version` is `data_version` from `domain.yaml`. It is `null` if no data was referenced.
- Input errors (missing required fields, out of range, unknown fields, unknown IDs, both forms given) produce a result with `isError: true` that states in Japanese which field is wrong. The server keeps running. The MCP SDK's (English) schema validation is disabled, and the same conditions are validated in the tools.

### Notes on stdio

Standard output is reserved for the MCP protocol. No banner is printed (`spring.main.banner-mode=off`), no web server is started (`spring.main.web-application-type=none`), and logs go only to standard error via `logback-spring.xml`.

## Tests

| Kind | Contents |
|---|---|
| Unit tests (JUnit 5) | Boundary values, input validation |
| Property tests (jqwik) | Probability within [0, 1], monotonic in the number of pulls, hard pity always yields the top rarity, monotonic in attack, etc. |
| Contract tests | Checks every case in `domains/wuwa/golden/*.yaml`. The same files are also checked by the Python reference implementation |
| Architecture (ArchUnit) | `domain` does not depend on calculation packages; `calc` does not depend on Spring, the MCP SDK or `app`; `app.tool` / `app.data` do not depend on frameworks; no cyclic dependencies |
| MCP layer | Passes golden case inputs to the MCP tools (through the adapter) and checks the results (`gacha` is also checked with Monte Carlo); data references and `unverified_inputs`; errors for invalid input; shape of the result JSON |
| Consistency | The three Monte Carlo methods agree exactly with the same seed, and agree with the exact solution within the error margin |

Quality gates: Spotless (google-java-format), Error Prone (warnings treated as errors), JaCoCo (fails below 90% line coverage).
The only class excluded from coverage is the Spring Boot application class (`McpServerApplication`). Because it starts a stdio server, it is not started in unit tests; it is verified by the end-to-end tests that launch the jar over stdio.

## Running

Can be run with Docker without installing a JDK on the host.

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check        # tests, formatting, static analysis, coverage
# Benchmarks (speed comparison of the three methods)
#   ... gradle:8-jdk21 ./gradlew jmh
```

With JDK 21 installed locally, `./gradlew check` alone is enough.

### MCP server

```bash
cd services/calc-engine
./gradlew bootJar                      # produces build/libs/calc-engine-mcp.jar
cd ../..                               # start from the repository root (same as config/services.yaml)
ECHOLAB_DATA_ROOT=domains java -jar services/calc-engine/build/libs/calc-engine-mcp.jar
```

Since it speaks MCP (JSON-RPC) over standard input/output, it is normally started as a child process by the Python core (`core/gateway/mcp_backend.py`) using the settings in `config/services.yaml`.
`./gradlew jar` also produces a plain jar without Spring Boot (`build/libs/calc-engine-<version>.jar`).

## Known limitations

- The numbers in `domains/wuwa/data/v2.x` are **unverified samples** (`verified: false`). The formulas are generic models; supply the game's actual formulas and constants only after checking them.
- The defense and resistance multipliers are generic models. If a game uses different formulas, swap out the multiplier functions (this is why each multiplier is a separate function).
