# domains/mortgage — 领域包②：房贷还款计算示例

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

> **这只是计算示例，不构成金融建议。** 它是固定利率、按月还款的简单模型，给出不舍入到日元的理论值。
> 实际的还款额与条件请向金融机构确认。回答末尾也必定附上这一注记（`domain.yaml` 的 `answer_note`）。

用于展示不改动核心一行代码即可添加第二个领域的最小示例（ADR-0003、[ADR-0009](../../docs/adr/zh-CN/0009-房贷领域包与核心零改动.md)）。

## 工具

| 工具 | 输入 | 结果字段 |
|---|---|---|
| `mortgage.equal_payment`（等额本息） | `principal`（日元）・`annual_rate`（小数，0.015 = 年 1.5%）・`years` | `monthly_payment`・`total_payment`・`total_interest` |
| `mortgage.equal_principal`（等额本金） | 同上 | `first_payment`・`last_payment`・`total_payment`・`total_interest` |
| `mortgage.prepayment`（部分提前还款） | 同上 ＋ `after_months`（已还期数）・`prepay_amount`（日元）・`method`（`shorten_term` 缩短期限型／`reduce_payment` 减少月供型） | `balance_before`・`monthly_payment_after`・`remaining_months_after`・`total_interest_before`・`total_interest_after`・`interest_saved`・`months_saved` |

差值（例如两种还款方式的利息差）由核心的比较工具 `compare.diff`・`compare.ratio` 求出。

## 结构

| 位置 | 内容 |
|---|---|
| `domain.yaml` | 领域包的清单。声明工具、提示词和回答注记。不带数据 |
| `calc/loan.py` | 计算。`Decimal`（有效位数 34），输出为小数 6 位・ROUND_HALF_EVEN。缩短期限型逐月推进余额，最后一期只支付剩余本金和利息 |
| `calc/server.py` | MCP 服务器（stdio）。由核心的网关作为 `config/services.yaml` 中的 `mortgage-calc`（`python -m domains.mortgage.calc`）启动 |
| `calc/schemas/` | 工具的输入 Schema（JSON Schema）。网关在调用前检查 |
| `golden/` | 黄金用例。每个工具都有手算或解析解的用例 |
| `prompts/system.md` | 领域的系统提示词（工具的分工） |
| `examples/compare_methods.yaml` | 脚本模式的演示（无需 API 密钥） |

## 运行

```bash
.venv/bin/python -m core.agent "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？" \
  --domain mortgage --llm scripted --script domains/mortgage/examples/compare_methods.yaml
.venv/bin/python -m core.evals --cases evals/faithfulness/mortgage.yaml   # 脚本模式的评估（5 个用例）
.venv/bin/pytest tests/test_mortgage_pack.py                              # 实现・MCP 服务器・评估的测试
```

## 模型不包含的内容

日元以下的取整、按日计息、奖金月还款、浮动利率与利率调整、手续费、税金（如房贷减税）、团体信用人寿保险。
