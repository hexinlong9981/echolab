[日本語](../0014-Vertex-AIのGemini適応層.md) ｜ [English](../en/0014-vertex-ai-gemini-adapter.md) ｜ **中文**

# ADR-0014: Vertex AI 的 Gemini 适配层（真实 LLM 评估与利用 GCP 免费额度）

- 状态: 采用
- 日期: 2026-10-04

## 背景

M2（[ADR-0008](0008-M2的结构与契约.md)）中实现的真实 LLM 评估仅针对 Claude（Anthropic API）。但 Anthropic API 为按量计费，需绑定信用卡预充值。
同时，本项目拥有 Google Cloud 免费试用额度（约 4.7 万日元），利用 Vertex AI 的 Gemini API 即可零自费开展真实的 LLM 评估。
此外，在未来的多提供商适配规划中，在不同的 LLM 架构上验证核心不变量（ADR-0008：LLM 不写数字，只引用确定性工具输出）也具有重要工程意义。

## 决定

| 项目 | 决定 |
|---|---|
| SDK 库 | 采用官方统一 SDK `google-genai`（v2），以 Vertex AI 模式（`vertexai=True`）运行 |
| 认证机制 | 支持 Google Cloud 标准的应用默认凭据（ADC）及环境变量（`GCP_PROJECT_ID`、`GCP_REGION`） |
| 模型选型 | 默认采用 `gemini-2.5-flash`（低价、快速、函数调用精准），亦可指定 `gemini-2.5-pro` |
| 自动函数调用 | 禁用自动函数调用（`disable=True`），由 Agent 循环集中管理工具准入、执行与打回重试 |
| 思考块处理 | 将 Gemini 2.5 的内部思考（`thought=True`）从回答正文（`texts`）中剥离，防止验证器误判推导过程中的数字；在历史（`raw_content`）中完整保留带有思考签名的响应 |
| 计费与上限 | 在 `config/budget.yaml` 中录入 Gemini 各模型的输入、输出与缓存费率，受 `Budget` 日次/月次上限管控 |
| CLI 与评估 | 新增 `--llm gemini` 及 `--model` 参数，同时适用于 `core.agent` 与 `core.evals` |

严守领域包隔离要求（不修改 `domains/`），在 `core/agent/llm/gemini.py` 中作为通用核心层独立实现。

## 理由

- `gemini-2.5-flash` 极具成本优势（每百万 Token 输入 $0.075 / 输出 $0.30），执行全部 8 项忠实度评估耗费仅约 $0.003（不足 0.5 日元），可在试用额度内充裕评测。
- Gemini 2.5 具备自主思考能力，若推导数字混入正文，ADR-0008 验证器会因“存在未核验数字”而退回。显式剥离思考块既保留了推理能力，又闭环了数字确定性引用。
- 借助 `google-genai` 的非同期客户端（`client.aio`），与现有 `loop.py` 自然集成，无额外子进程开销。

## 否决的方案

| 方案 | 否决原因 |
|---|---|
| 仅支持 Claude（Anthropic API） | 无法使用 GCP 免费试用额度，需自掏腰包预充值（违背用户费用优先方针） |
| Google AI Studio（API 密钥方式） | 无法消耗 Vertex AI 试用额度，且需单独分发维护 API 密钥 |
| 启用自动函数调用（AFC） | 会导致 SDK 直接调用工具，绕过网关默认拒绝、Schema 校验、出处编号与验证器退回机制（违反 ADR-0008） |
| 彻底关闭思考（budget=0） | 可能会削弱模型的语义理解与工具选取精度；允许思考但从检验范围剔除是最佳方案 |

## 影响

- 新增文件：`core/agent/llm/gemini.py`、`tests/core/test_llm_gemini.py`、`evals/reports/gemini-baseline.md`。
- 变更文件：`requirements.txt`（新增 `google-genai`）、`config/budget.yaml`（定价表）、`core/agent/` 和 `core/evals/`（CLI 参数）。
- 验证结论：经实机 `python -m core.evals --llm gemini` 验证，忠实度达成 1.000，流程全通。
