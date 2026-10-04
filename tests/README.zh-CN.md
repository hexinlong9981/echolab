# tests/ — 跨仓库的测试（Python）

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

*本文为译文，以日文版为准。*

## 契约与数据

| 文件 | 内容 |
|---|---|
| `test_golden_schema.py` | 用 JSON Schema 检查黄金用例（`domains/*/golden`、`core/golden`）与领域数据的格式。要求 `verified: false` 的值其出处为 TODO。要求每个工具至少有 1 个 `derivation` 不是 `reference`（手算或闭式解）的用例。用违规示例与正常示例确认 `verified: true` 的出处规则（ADR-0006）确实生效 |
| `test_golden_reference.py` | 用 Python 参考实现（`reference/calc_reference.py`）重新计算黄金用例的期望值。比较工具的用例（`core/golden`）与 `core.compare` 核对。与 Java 的契约测试一起，保证 YAML、Java、Python 三者一致 |
| `test_domain_manifest.py` | 用 `schemas/domain.schema.json` 检查领域包的清单（`domains/*/domain.yaml`）。确认 `name` 与目录名一致、`data_dir`・`golden_dir`・`prompts_dir` 存在、黄金用例中的工具全部已在 `tools` 中声明、工具名没有重复 |

## 核心（`core/`）的单元测试：`tests/core/`

不使用 API 密钥，也不使用 Java。LLM 替换为脚本（`ScriptedLLM`）或伪造的 SDK 客户端，计算服务替换为伪造实现。

| 文件 | 内容 |
|---|---|
| `fakes.py` | 测试用的伪计算服务（`FakeCalcBackend`）。不启动 Java，用参考实现计算。CLI 的 `--fake-backend` 与脚本模式的评估也会使用 |
| `stub_mcp_server.py` | 测试用的小型 stdio MCP 服务器。返回与 calc-engine 相同形式的结果（`ToolEnvelope` 的 JSON） |
| `test_gateway.py` | 网关：许可列表（未声明、未公开的工具既不展示也不允许调用）・输入 Schema 校验（违规时不调用服务）・调用 ID 与出处 ID 的分配（并发下也唯一）・比较工具的出处 ID 解析与未确认数据的传递 |
| `test_gateway_budget.py` | 成本台账与上限：按价格表计算・每日与每月上限・按 UTC 划分日与月・台账无法读取时停止・价格表中没有的模型按安全侧估算・通过环境变量覆盖 |
| `test_mcp_backend.py` | 针对 `stub_mcp_server.py` 运行 `McpStdioBackend`：工具列表与调用・启动失败的报告・按 `config/services.yaml` 启动 |
| `test_compare.py` | 比较工具（差值、比值、增长率）的计算・舍入・除以 0 |
| `test_verifier.py` | 渲染器的格式（位数、百分比、千位分隔符、舍入）与验证器的判定（占位符格式・未知出处 ID・无出处的数字・引用问题中的数值・许可列表・未确认数据的注释） |
| `test_agent.py` | Agent 的往返：并行工具调用・从工具错误中恢复・退回与重试・切换为不含数值的回答・成本上限・往返次数上限・拒绝与输出截断・LLM 失败 |
| `test_llm_anthropic.py` | Claude 的 LLM 实现：请求构造（模型、思考深度、回退、提示词缓存）・响应的规范化・回退时的计费・拒绝与 API 错误 |
| `test_llm_scripted.py` | 脚本 LLM：应答顺序・`expect` 的核对・示例脚本的加载 |
| `test_trace.py` | 执行追踪：每行一个事件的 JSONL・契约类型的序列化・Agent 记录的事件内容 |
| `test_evals.py` | 以脚本模式运行全部数值忠实度评估用例，确认结果与已提交的 `evals/reports/scripted-baseline.md` 一致 |

## 领域包②：房贷（ADR-0009）

不使用 Java。领域包的 MCP 服务器（Python）以真实的子进程启动，因此在 CI 的 `python` 作业中每次运行。

| 文件 | 内容 |
|---|---|
| `reference/mortgage_reference.py` | 房贷的参考实现。用与领域包实现（`Decimal`，逐月推进余额）不同的方法（`float`，用余额公式和对数求月数）计算 |
| `test_mortgage_pack.py` | 领域包实现与黄金用例的核对・输入错误的说明・经网关启动真实 MCP 服务器后的黄金用例核对与错误・Agent 的往返与回答注记・脚本模式的评估（`evals/faithfulness/mortgage.yaml`）与基线 |
| `test_pack_isolation.py` | 在临时 git 仓库中检查 CI 的"领域包的变更不修改核心"检查（`.github/scripts/check_pack_isolation.py`）的规则 |

## 截图读取与注入评估（ADR-0010）

| 文件 | 内容 |
|---|---|
| `test_vision.py` | `servers/vision_mcp`：用模板取出字段（用 OCR 记录 `.ocr.txt` 测试）・图片中写入的指示不进入结果・超出范围与重复的错误・图片路径的限制（根目录之外・符号链接・扩展名）・真实的 Tesseract 与 MCP 服务器・模板的 Schema（`schemas/vision_template.schema.json`） |
| `test_redteam.py` | 以脚本模式运行注入评估（`evals/redteam/cases.yaml`）：攻击无一成功・图片中的文字不进入工具结果・基线 |

真实 OCR 的测试需要 Tesseract（含日语数据）。没有时跳过（CI 中用 `ECHOLAB_OCR_REQUIRED=1` 让它失败而不是跳过）。

## 网页界面（ADR-0011）

| 文件 | 内容 |
|---|---|
| `test_web_api.py` | `servers/web_api`：导出（全部演示与评估的轨迹，不含本机路径）・请求检查（未知的 LLM・剧本・过长的问题・领域）・本机 API（只监听 127.0.0.1・拒绝其他网站的 `Origin` 与错误的 `Content-Type`・运行剧本演示） |
| `web/src/replay.test.ts` | 界面端（Vitest，`cd web && npm test`）：执行轨迹事件 → 回放步骤（到达的方框・拒绝・退回・出处表）、箭头端点的计算 |

## 端到端测试：`tests/e2e/`

`test_mcp_e2e.py` 按照 `config/services.yaml` 启动真实的 calc-engine（MCP 服务器的 jar）。

- 经由 MCP 核对全部黄金用例（继 Java 单元测试、Python 参考实现之后的第 3 处核对）。
- 确认启动后立即进行的并行调用・非法输入的错误・引用数据时未确认数据的传递与注释。
- 使用脚本 LLM，在真实计算服务之上跑通 Agent 的往返。

运行需要 jar 与 JDK 21。缺少任一项时跳过（在 CI 中通过 `ECHOLAB_E2E_REQUIRED=1` 使其失败而不是跳过）。

```bash
(cd services/calc-engine && ./gradlew bootJar)      # build/libs/calc-engine-mcp.jar
export JAVA_HOME=/path/to/jdk-21 PATH="$JAVA_HOME/bin:$PATH"
.venv/bin/pytest -m e2e
```

在 CI 中，`test.yml` 的 `python` 作业运行 `pytest -m "not e2e"`，`e2e` 作业先构建 jar 再运行 `pytest -m e2e`。

`pack-isolation` 作业在 git 历史中检查领域包的变更没有修改核心（ADR-0009）。

`web.yml` 工作流导出网页界面的数据、做类型检查、运行 Vitest 并构建；在 main 上发布到 Cloudflare Pages（有 Secrets 时）。
