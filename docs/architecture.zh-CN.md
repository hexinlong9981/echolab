[日本語](architecture.md) ｜ [English](architecture.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

# 架构

EchoLab 是一个“**数值由确定性工具计算，AI 只负责理解与说明**”的 AI 助手（ADR-0001）。

## 整体概览

实线框为已实现部分（M1、M2），虚线框为计划部分（括号内为实现该部分的里程碑）。

```mermaid
flowchart TB
  CLI["CLI（M2）<br/>python -m core.agent"]
  UI["Web UI（M5・React + TypeScript）<br/>对话・追踪回放・评估仪表盘"]
  subgraph core["core/（领域无关・Python・M2 起）"]
    AG["Agent<br/>并行调用工具 → 验证 → 退回"]
    GW["策略网关<br/>允许列表・模式・预算"]
    VF["数值追踪验证器・渲染器<br/>占位符・未确认数据的注记"]
    CMP["比较工具 compare.*<br/>差・比・增长率"]
    EV["评估<br/>数值忠实度"]
    TR["执行追踪"]
  end
  subgraph tools["MCP 工具"]
    CE["calc-engine（Java 21）<br/>伤害・评分・抽卡<br/>MCP 服务器（stdio）"]
    VM["vision_mcp（M4・Python）"]
  end
  subgraph domains["domains/（领域包）"]
    D1["① wuwa（M1 起）"]
    D3["② mortgage（M3）"]
  end
  CLI --> AG
  UI --> AG
  AG --> GW --> CE & CMP & VM
  AG --> VF
  AG --> TR
  domains -. "在 domain.yaml 中声明" .-> GW
  EV -. "以评估用例执行" .-> AG

  classDef planned stroke-dasharray: 5 5
  class UI,VM,D3 planned
```

## 单次提问的流程

```mermaid
sequenceDiagram
  participant U as 用户
  participant A as Agent
  participant L as LLM（Claude）
  participant G as 网关
  participant C as calc-engine（MCP）
  participant K as 比较工具（compare.*）
  participant V as 验证器・渲染器
  U->>A: 提问
  A->>A: 检查费用上限
  A->>L: 提问・工具定义
  L-->>A: 工具调用（可多个）
  A->>G: 调用（并行）
  G->>G: 检查允许列表（domain.yaml）・输入模式，分配调用 ID
  G->>C: 计算
  C-->>G: values（十进制字符串）+ unverified_inputs
  G-->>A: 带出处 ID（如 c1.total）的值
  opt 需要差・比・增长率时
    L-->>A: compare.diff / compare.ratio（输入为出处 ID）
    A->>G: 调用
    G->>K: 将出处 ID 解析为值并计算
    K-->>A: 派生值（带出处 ID・未确认数据标记为输入的并集）
  end
  L-->>A: 回答模板（数值以 [[c1.total|0]] 引用）
  A->>V: 模板・提问・本次提问的出处
  V->>V: 检查占位符格式与出处 ID<br/>其他数字只允许引用提问中的数值或属于允许列表
  alt 不通过
    V-->>A: 指出问题
    A->>L: 退回（超过 2 次上限后返回不含数值的固定回答）
  else 通过
    V->>V: 将占位符替换为数值，若源自未确认数据则添加注记（ADR-0006）
    V-->>A: 回答
  end
  A-->>U: 回答 + 所引用出处的表格
```

验证器的方针见 ADR-0005，占位符方式与组件间的契约见 ADR-0008。要点如下。

| 规则 | 内容 |
|---|---|
| LLM 不做计算 | 包括四则运算在内，派生值均由 `core` 的比较工具（领域无关）计算 |
| LLM 不写数值 | 回答是模板，数值通过占位符 `[[<出处 ID>]]`・`[[<出处 ID>\|<格式>]]` 引用。数值由渲染器确定性地填入 |
| 出处 ID | 网关为工具结果中的每个数值分配 `<调用 ID>.<字段>`（例 `c1.total`）。计算服务不知道 ID |
| 允许的数字 | 占位符以外，只允许引用提问中的数值（对千位分隔符・`%` 做规范化）以及允许列表中的数字（列表项编号、10 以下的整数 + 量词：日文「つ・点・種類・位・番目」、中文「个・种・项・条・步」，或英文名词 ways・points・steps 等） |
| 格式 | 省略时最多保留 2 位小数，`N` 为 N 位小数，`%N` 为保留 N 位小数的百分数。舍入方式为 ROUND_HALF_EVEN |
| 未确认数据 | 将 `unverified_inputs` 传播到出处，对引用了它们的回答由渲染器添加注记（ADR-0006） |

## 当前状态（M2）

M1（计算服务）与 M2（CLI 纵向切片）已实现。仓库中只放置已实现部分的目录（ADR-0007）。

| 位置 | 内容 |
|---|---|
| `core/` | 领域无关的核心（Python）。组件见下一节的表格 |
| `config/` | `services.yaml`（工具服务的启动方式）・`budget.yaml`（费用上限与价格表） |
| `services/calc-engine` | Java 21 的计算库（`dev.echolab.calc`，不依赖框架）与 MCP 服务器（`dev.echolab.app`，ADR-0004） |
| `domains/wuwa` | `domain.yaml`・黄金用例（带 `derivation`）・未确认的示例数据（`verified: false`）・提示词 |
| `evals/` | 数值忠实度的评估用例（`faithfulness/cases.yaml`）与汇总后的报告（`reports/`） |
| `tests/` | 模式检查・与 Python 参考实现的对照・`core` 的单元测试（`tests/core/`）・端到端测试（`tests/e2e/`） |
| `.github/workflows` | `test.yml`（ruff・pytest・脚本模式的评估、启动 jar 的端到端测试）与 `java.yml`（`./gradlew check`・`bootJar`） |

每个黄金用例都写明 `derivation`（`hand`：手算／`closed_form`：闭式表达式／`reference`：参考实现的输出），
并且每个工具至少有 1 个非 `reference` 的用例（以避免与参考实现循环论证）。
领域的黄金用例在 3 处对照：Java 契约测试、Python 参考实现、经由 MCP 的端到端测试。
比较工具的黄金用例位于 `core/golden/`，与 `core.compare` 对照。
`domain.yaml` 用 `tests/schemas/domain.schema.json` 检查（`tests/test_domain_manifest.py`）。

## 路线图与今后的结构

方针见 ADR-0007：在横向扩展功能之前，先打通端到端。
不为未实现的部分创建目录，计划只写在本节中。目录在实现时再创建。

| 阶段 | 内容 | 状态 |
|---|---|---|
| M1 | calc-engine（Java）・黄金用例・CI | 完成 |
| M2 | 纵向切片：CLI → 网关 → calc-engine（MCP）→ 数值追踪验证器 → 带出处的回答。数值忠实度评估・执行追踪 | 完成 |
| M3 | 领域包②：房贷试算（最小示例）。在 CI 中检查“核心差异为零” | 计划中 |
| M4 | 截图读取・注入攻击评估集（将脚本模式加入 CI） | 计划中 |
| M5 | Web UI・追踪回放・评估仪表盘・公开演示 | 计划中 |

### M2：纵向切片（提问 → 带出处的回答）：已实现

`core/` 中完全不引入鸣潮、房贷之类的领域概念。
各领域的知识在 `domains/<名称>/domain.yaml` 中声明，核心只读取它（ADR-0003）。
组件的划分与边界契约见 ADR-0008。

| 位置 | 职责 |
|---|---|
| `core/contracts.py` | 组件间的契约：工具结果（`ToolEnvelope`）・工具服务的连接（`ToolBackend`）・带出处的值（`SourceValue`）・占位符格式 |
| `core/gateway/gateway.py` | LLM 与工具之间唯一的入口：`domain.yaml` 的允许列表（默认拒绝）・输入的 JSON Schema 验证・调用 ID 与出处 ID 的分配・比较工具的出处 ID 解析 |
| `core/gateway/mcp_backend.py` | stdio 的 MCP 客户端。按照 `config/services.yaml` 以子进程方式启动服务。单次调用等待响应的上限为 30 秒 |
| `core/gateway/budget.py` | 费用台账（`.echolab/costs.jsonl`）与每日・每月上限（默认 1 USD・10 USD，按 UTC 划分）。对价格表中没有的模型的计费，按表中最高价格估算 |
| `core/compare/` | 比较工具 `compare.diff`（差）・`compare.ratio`（比与增长率）。输入只能是出处 ID。精度方针与 calc-engine 相同（16 位有效数字・6 位小数・ROUND_HALF_EVEN） |
| `core/verifier/` | 回答模板的验证（`verify.py`）与将占位符替换为数值的渲染器（`render.py`） |
| `core/agent/` | Agent 的往返（`loop.py`）・CLI（`python -m core.agent`）・LLM 抽象（`llm/`：Claude 与脚本 LLM）・核心系统提示词（`prompts/core.md`） |
| `core/trace/` | 执行追踪。将单次提问记录到 `.echolab/traces/<执行 ID>.jsonl` |
| `core/evals/`・`evals/` | 数值忠实度评估（`python -m core.evals`）。用例位于 `evals/faithfulness/cases.yaml` |
| `services/calc-engine`（`dev.echolab.app`） | Spring Boot + Spring AI 的 MCP 服务器（同步・stdio）。只调用 `calc` 的公开 API，不包含计算公式。在结果中附加 `unverified_inputs`（ADR-0006） |

Agent 的往返流程如下。

1. 每次调用 LLM 之前检查费用上限。若已达到上限，则不调用 LLM 直接结束。
2. LLM 请求的工具调用由网关并行执行，结果（带出处 ID 的值）汇总在 1 条消息中返回。
   工具输入的错误不作为异常抛出，而是作为错误结果返回给 LLM，让其重新调用。
3. 未调用工具而直接返回的文本视为回答模板，交给验证器检查。不通过则附上指出的问题并退回。
   退回超过 2 次后，以不含数值的固定回答结束。
4. 每次提问调用工具的往返最多 6 次。遇到 LLM 拒绝（`refusal`）或输出被截断（`max_tokens`）时，不执行中途的工具调用直接结束。

LLM 为 Claude（`claude-opus-5-5`），中间隔着一层抽象（`core/agent/llm/`）。测试・CI・演示中使用按脚本应答的 LLM
（`ScriptedLLM`），无需 API 密钥即可重现相同的往返。

**数值忠实度**是指“返回给用户的回答中，不含任何无出处数值的回答所占的比例”。
对于通过验证的回答，用验证器再次检查其模板；对于固定回答，确认其中不含数字。这是一个用于确认其在机制上必然为 1.0 的指标。
同时汇总退回率（被退回的草稿 / 草稿）与费用。

- 脚本模式的评估（8 个用例）在 CI 中每次通过 pytest 执行，并将汇总结果与 `evals/reports/scripted-baseline.md` 对照。
- 使用真实 LLM 的评估（`--llm anthropic`）在本地手动执行，只将汇总后的报告提交到 `evals/reports/`。原始记录（`evals/reports/raw/`）不提交。
- CI 不持有 API 密钥。

来自外部的字符串（工具结果・用户输入）一律作为数据而非指令处理。

### M3：领域包②：房贷试算（最小示例）

用于展示“不改动核心一行代码，用约 300 行即可添加新领域”的最小示例（ADR-0003）。

- `domains/mortgage/`：计算等额本息与等额本金的比较，以及提前还款的效果（`calc/`，Python）。包含 `golden/`・`prompts/`・`domain.yaml`。
- 在 CI 中检查添加该领域包的变更在 `core/` 中的差异为零。
- **这只是计算示例，不构成金融建议。** README 与回答中也会如此标示。

### M4：截图读取与评估流水线

| 计划位置 | 职责 |
|---|---|
| `servers/vision_mcp/` | 截图 → 结构化 JSON（带模式验证，Python） |
| `evals/redteam/` | 提示词注入的评估题（包含合成的截图，不使用游戏图片） |

分工与 M2 相同。CI 不持有 API 密钥，只执行脚本模式的评估与端到端测试。
使用真实 LLM 的评估在本地手动执行，只将汇总后的报告提交到 `evals/reports/`。

### M5：Web UI

`web/`（React + TypeScript）。提供对话、执行追踪回放（React Flow）与评估仪表盘。
用 Vite 构建的静态文件部署在 Cloudflare Pages 上。

## 语言分工

| 部分 | 语言 | 理由 |
|---|---|---|
| 计算服务 | Java 21 | 基于类型的穷尽性・`BigDecimal`・并行性能（ADR-0002） |
| Agent・评估・比较工具 | Python | AI 与评估相关的工具丰富 |
| 界面 | TypeScript（React） | 对话 UI・流程图相关的组件丰富 |

语言之间的契约是黄金用例的格式（`tests/schemas/golden.schema.json`）。
核心与领域包之间的契约是 `domain.yaml` 的格式（`tests/schemas/domain.schema.json`）。
核心与计算服务之间的契约是 MCP 结果的 JSON（`core/contracts.py` 中的 `ToolEnvelope`，ADR-0008）。

## 已知限制

M2 时点的限制及其影响范围。

| 项目 | 内容 |
|---|---|
| 对同一服务的调用为串行 | Agent 会并行发出工具调用，但 `McpStdioBackend` 对同一服务的调用逐个发送。原因是 MCP Java SDK 的 stdio 传输在启动后立即并发写出响应时，可能会丢失响应。计算在数毫秒内完成，对等待时间几乎没有影响 |
| 费用上限在调用前检查 | 上限在调用 LLM 之前检查。单次调用的费用要到收到响应后才能知道，因此最后一次调用可能使费用略微超出上限 |
| 费用台账为本地 JSONL | 台账（`.echolab/costs.jsonl`）是以单机・单用户使用为前提的文件，不做跨进程的互斥控制。若同时运行多个进程，上限判定可能遗漏彼此的用量 |
| 验证器检查的数字范围 | 验证器作为数值检测的是阿拉伯数字（含全角）。不检测汉字数字（如「三」）。此外，与提问中数值相等的数字，无论出现在什么上下文中都视为引用而允许 |
| 示例数据未确认 | `domains/wuwa/data` 中的值是未确认的示例（`verified: false`）。使用这些数据的回答会附带注记（ADR-0006） |
