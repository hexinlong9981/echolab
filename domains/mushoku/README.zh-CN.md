# domains/mushoku — 领域包③：无职转生设定考证（非官方）

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

> **非官方同人作品。** 《无职转生～到了异世界就拿出真本事～》的权利归原作者、出版社、动画制作方等各权利人所有。
> 不收录原作正文、台词、插图和动画画面，只收录自己写的简短摘要以及卷・集编号。
> **资料全部是凭记忆写的未确认草稿**（`verified: false`），可能有错误。地图的天数是自定的大致估计。

回答设定、时间线、行程问题的领域包（M6、[ADR-0012](../../docs/adr/zh-CN/0012-无职转生领域包与防剧透.md)）。
看点是**防剧透**：与业务中"按用户权限过滤检索结果"相同的机制，在检索层强制执行。

## 防剧透的机制

- **进度由用户指定**：`--context progress=novel:5`（小说看到第 5 卷）、`--context progress=anime:2-12`（动画看到第 2 季第 12 集）。
  `progress` 是 `domain.yaml` 的 `user_context`，网关不让 LLM 看到它，而是自己加到工具输入中；LLM 送来就拒绝。
- **只按声明的媒体过滤**：小说与动画之间不换算。该媒体没有标注的条目一律不返回（默认拒绝）。
- **看不到＝不存在**：还没看到的人物・事件・地点，与资料中没有的条目返回同样的错误。
- **也防止身份剧透**：会暴露身份的别名（如菲茨）只在揭晓的卷・集之后才使用。事实的标签只限于该句本身能看出的内容。
- **限制**：LLM 凭自己的知识写出的"不含数字的剧透句子"无法从结构上拦住（只靠提示词禁止）。含数字的会被验证器拦住。

## 工具

| 工具 | 内容 | 结果 |
|---|---|---|
| `lore.search` | 按关键词（全部包含）找事实，人物・地点的名字也能命中 | `values`：件数・各事实的卷（或季・集），`texts`：事实的句子（不含数字） |
| `timeline.age` | 某事件那一年某人物的年龄 | `age`・`birth_year`・`event_year`（甲龙历） |
| `timeline.span` | 两个事件之间的年数 | `years`・`from_year`・`to_year` |
| `map.route` | 在自制地图上的最短行程（只用看得到的路） | `total_days`・`legs`，路线在 `texts` |

## 结构

| 位置 | 内容 |
|---|---|
| `data/draft-1/` | 事实（40）・人物（18）・事件（3）・地点（8）与道路（7）。Schema 在 `schema/` |
| `service/` | 检索・时间线・行程（`lore.py`）与 MCP 服务器（`server.py`，`config/services.yaml` 中的 `mushoku-lore`） |
| `golden/` | 黄金用例（手算）。参考实现：`tests/reference/mushoku_reference.py` |
| `prompts/system.md`・`examples/` | 提示词与剧本演示 |

```bash
.venv/bin/python -m core.agent "転移事件のとき、ルーデウスは何歳だった？" --domain mushoku \
  --context progress=novel:3 --llm scripted --script domains/mushoku/examples/teleport_age.yaml
.venv/bin/python -m core.evals --cases evals/redteam/spoilers.yaml      # 诱导剧透的评估（7 个用例）
```

核对资料后，把该条目改为 `verified: true`，在 `source` 写具体的卷・集位置，在 `checked_at` 写确认日期（Schema 要求必填）。
