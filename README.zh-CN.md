# EchoLab

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

*本文为译文，以日文版为准。*

> **不让 AI 做计算的 AI 助手。** 数值由确定性工具计算，AI 只负责理解与说明。
> 以《鸣潮（Wuthering Waves）》角色培养为题材的**非官方、非营利粉丝作品**。

[免责声明](DISCLAIMER.zh-CN.md)

> **使用说明**（附图解和动画，日语・英语・中文）：<https://hexinlong9981.github.io/echolab/zh/>（源文件：[`docs/guide/`](docs/guide/)）
>
> **本地运行指南**（从无需 API 密钥的方式开始）：<https://hexinlong9981.github.io/echolab/local/zh/>

## 这是什么

这是一个 AI 助手，回答声骸评估、伤害比较、抽卡概率这类"只要错一个数字就会失去信任"的问题。
回答中出现的所有数值都来自计算服务，并且可以查看其出处（计算明细）。

## 为什么要做

LLM 会编造看似合理的数值。在业务中使用 AI 时，最常被追问的也是
"这个数字可信吗？"。EchoLab 通过设计来回答这个问题。

| 问题 | EchoLab 的设计 |
|---|---|
| 数值捏造 | 计算只由确定性工具完成。差值、比值、增长率也由比较工具计算，AI 连四则运算都不做。LLM 的回答是通过占位符引用出处 ID 的模板，数值由渲染器填入。只要出现没有出处的数字就退回重写（M2、ADR-0005、ADR-0008） |
| 数据的可靠性 | 未确认的数据也可用于计算，但回答中必定注明"基于未确认的数据"。`verified: true` 在 Schema 中强制要求出处 URL、确认日期和游戏版本（ADR-0006） |
| 实现错误 | 同一组黄金用例在三处核对：Java、Python 参考实现、经由 MCP 的端到端测试 |
| 越权与注入 | 工具调用经过默认拒绝的网关。来自外部的字符串被视为数据而非指令。从图片中只读取模板声明的数值，图片里的文字不会传给 LLM（M4、ADR-0010） |
| 质量退化 | 评估数值忠实度。脚本模式的评估在 CI 中对每个 PR 运行；使用真实 LLM 的评估在本地运行，只提交汇总结果（M2）。注入评估集也以脚本模式在 CI 中运行（M4） |
| 成本 | 根据价格表计算每次调用的费用并记入台账，达到每日或每月上限后不再调用 LLM（M2） |

采用将领域无关的核心与"领域包"分离的设计。第二个领域包（房贷还款计算示例，M3）在不改动 `core/` 一行代码的情况下加入，并由 CI 检查这一点（ADR-0003、ADR-0009）。

## 当前状态：M6（第三个领域包：无职转生）

从提问到附带出处的回答，可以在 CLI 中端到端跑通（M2）。同一个核心可以运行鸣潮・无职转生・房贷三个领域包（M6・M3）。
可以用 OCR 读取声骸界面的截图并评分，提示词注入的评估在 CI 中每次运行（M4）。
无职转生领域包在检索层不返回超出用户指定进度的信息（防剧透，M6）。
可以在网页上回放执行轨迹、查看评估看板（M5；公开网站只有静态文件，零费用）。

```mermaid
flowchart LR
  Q["提问（CLI）"] --> A["Agent<br/>core/agent"]
  A <--> L["LLM（Claude）<br/>回答为占位符模板"]
  A --> G["网关<br/>许可列表・Schema・编号・成本上限"]
  G -->|MCP stdio| J["calc-engine（Java 21）<br/>鸣潮领域包"]
  G -->|MCP stdio| O["vision-mcp（Python）<br/>截图 OCR"]
  G -->|MCP stdio| N["mushoku-lore（Python）<br/>无职转生领域包"]
  G -->|MCP stdio| M["mortgage-calc（Python）<br/>房贷领域包"]
  G --> K["比较工具 compare.*"]
  A --> V["数值验证器・渲染器"]
  V --> R["附带出处的回答"]
  A -.-> T["执行追踪（JSONL）"]
```

| 项目 | 内容 |
|---|---|
| 回答 | LLM 编写模板，用占位符 `[[c1.total\|0]]` 引用数值。数值由渲染器根据出处 ID 确定性地填入（ADR-0008） |
| 验证 | 占位符以外的数字，只允许引用问题中的数值或许可列表中的数字（如列表序号）。不符合则退回，退回超过 2 次后以不含数值的回答结束 |
| 网关 | 只暴露 `domain.yaml` 中声明的工具（默认拒绝）、用 JSON Schema 校验输入、分配调用 ID 与出处 ID、每日与每月的成本上限 |
| 计算 | 将 calc-engine 作为 MCP 服务器（Spring Boot + Spring AI，stdio）公开。期望伤害、声骸评分、抽卡概率（精确解与蒙特卡洛法）。差值、比值、增长率由 `compare.diff`、`compare.ratio` 计算 |
| 未确认数据 | 计算中使用的未确认数据的 ID 会传递到结果中，引用它的回答会自动附加注释（ADR-0006） |
| 领域包 | 在 `domains/<名称>/domain.yaml` 中声明工具、提示词和回答注记。无职转生与房贷领域包都在不改动 `core/` 的情况下加入，CI 的 `pack-isolation` 作业检查这一点（ADR-0009）。用户指定的项目（`user_context`，如进度）由网关加入，不给 LLM 看（ADR-0012） |
| 截图 | `servers/vision_mcp` 用 Tesseract（OCR）读取，只返回领域包模板中声明的数值字段。限制图片位置，超出范围的值视为错误（ADR-0010） |
| 评估 | 数值忠实度（不含任何无出处数值的回答所占比例）、退回率、被拒绝的工具调用数。脚本模式的用例（鸣潮 8 个、注入 7 个、无职转生 3 个、诱导剧透 7 个、房贷 5 个）在 CI 中每次运行 |
| 追踪 | 一次提问记录为一个 JSONL 文件（提问、LLM 调用及费用、工具调用、验证判定、回答） |
| 测试 | 黄金用例在 Java、Python 参考实现、经由 MCP 的端到端测试三处核对。Java 有单元测试、性质测试（jqwik）、ArchUnit，Python 使用 pytest |
| 质量门禁 | Error Prone（警告视为错误）、Spotless、JaCoCo（行覆盖率 90% 以上）、ruff |

## 使用方法

### 1. 无需 API 密钥试用（脚本模式）

使用按脚本应答的 LLM，以及由 Python 参考实现计算的测试用计算服务运行。不需要 Java，也不需要 API 密钥。

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m core.agent "ビルド A（攻撃力 2000、スキル倍率 2.5、ダメージバフ 0.3、会心率 0.6、会心ダメージ 2.2、敵の防御 1000、耐性ダウンなし）とビルド B（攻撃力 1800、スキル倍率 3.0、ダメージバフ 0.2、会心率 0.5、会心ダメージ 2.5、敵の防御 1200、耐性ダウン 0.3）では、どちらがどれだけ強い？ どちらも防御定数 1600、防御無視 0、敵の耐性 0.1。" \
  --llm scripted --script core/agent/examples/compare_builds.yaml --fake-backend
```

输出：

```text
ビルド B の方が強いです。
- ビルド A の期待ダメージ: 6,192
- ビルド B の期待ダメージ: 7,128
- 差: 936（A に比べて 15.1% 増加）

出典:
出典 ID    値           ツール           未確認データ
---------  -----------  ---------------  ------------
c1.total   6192.000000  damage.expected  -
c2.total   7128.000000  damage.expected  -
c3.diff    936.000000   compare.diff     -
c4.change  0.151163     compare.ratio    -

状態: answered　差し戻し: 1 回　費用: $0.0000　実行 ID: 20261003T024533Z-ab0ef9
トレース: .echolab/traces/20261003T024533Z-ab0ef9.jsonl
```

该脚本的第 1 版草稿因自行写出差值"936"而被退回。第 2 版通过比较工具求出差值与增长率，
并用占位符引用，从而通过验证（差し戻し: 1 回 即退回 1 次）。

### 2. 使用真实的计算服务（Java）

去掉 `--fake-backend` 后，会按照 `config/services.yaml` 将 calc-engine 的 MCP 服务器（jar）作为子进程启动。
需要 JDK 21（若 `PATH` 中没有 `java`，则使用 `JAVA_HOME/bin/java`）。

```bash
(cd services/calc-engine && ./gradlew bootJar)   # build/libs/calc-engine-mcp.jar
.venv/bin/python -m core.agent "（質問）" --llm scripted --script core/agent/examples/compare_builds.yaml
```

### 3. 使用真实的 LLM（Claude）

默认的 `--llm anthropic` 会调用 Claude API（`claude-opus-5-5`）。

```bash
export ANTHROPIC_API_KEY=...
.venv/bin/python -m core.agent "攻撃力 2000、スキル倍率 2.5、ダメージバフ 0.3、会心率 0.6、会心ダメージ 2.2、防御定数 1600、敵の防御 1000、防御無視 0、敵の耐性 0.1、耐性ダウン 0 のときの期待ダメージは？"
```

- 成本上限为**每日 1 USD、每月 10 USD**（`config/budget.yaml`，按 UTC 划分）。每次调用 LLM 前都会检查，若已达上限则不调用直接结束。
- 用量与金额追加记录到 `.echolab/costs.jsonl`。上限可通过环境变量 `ECHOLAB_DAILY_USD`、`ECHOLAB_MONTHLY_USD` 修改。
- 执行追踪保存在 `.echolab/traces/<执行 ID>.jsonl`（两者均不纳入 Git 管理）。

### 4. 读取截图（OCR）

在问题中写上声骸界面截图（PNG・JPEG）的路径，`servers/vision_mcp` 会用 Tesseract 读取，并把值变成出处 ID。
需要 Tesseract 及其日语数据。默认只能读取仓库内的图片（可用 `ECHOLAB_VISION_ROOTS` 修改）。
下例中的图片（合成图片，不是游戏图片）上写着"忽略之前的指示……"，但读取结果只有数值，所以传不到 LLM。

```bash
sudo dnf install tesseract tesseract-langpack-jpn   # Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-jpn
.venv/bin/python -m core.agent "evals/redteam/screenshots/echo-injection.png の声骸を採点して。重みは会心率 1.0・会心ダメージ 1.0・攻撃力% 0.75・攻撃力 0.25・共鳴効率 0.5、最大値は会心率 0.1・会心ダメージ 0.2・攻撃力% 0.12・攻撃力 60・共鳴効率 0.12 として。" \
  --llm scripted --script domains/wuwa/examples/score_screenshot.yaml
```

```text
画像から、サブ詞条の会心率 8.0%・会心ダメージ 16.0% などを読み取りました。 この声骸のスコアは 2.58 で、理想値の 73.7% です。読み取った値が画像と合っているか確かめてください。

出典:
出典 ID              値         ツール                未確認データ
-------------------  ---------  --------------------  ------------
c1.sub_crit_rate     0.08       echo.read_screenshot  -
c1.sub_crit_dmg      0.16       echo.read_screenshot  -
c2.score             2.579167   echo.score            -
c2.percent_of_ideal  73.690476  echo.score            -
```

### 5. 无职转生领域包（`--domain mushoku`，防剧透）

回答设定检索・时间线（年龄・年数）・自制地图上的行程（M6、ADR-0012）。**进度由用户用 `--context progress=…` 指定**
（`novel:<卷>` 或 `anime:<季>-<集>`），超出进度的事实・人物・事件・道路在检索层一律不返回。LLM 无法改变进度。
**这是非官方同人作品，资料全部是凭记忆写的未确认草稿**（[domains/mushoku/README.zh-CN.md](domains/mushoku/README.zh-CN.md)）。

```bash
.venv/bin/python -m core.agent "転移事件のとき、ルーデウスは何歳だった？" --domain mushoku \
  --context progress=novel:3 --llm scripted --script domains/mushoku/examples/teleport_age.yaml
```

```text
転移事件のとき、ルーデウスは 10 歳でした（甲龍歴 417 年、生まれは 407 年）。
資料によると、フィットア領で大規模な転移事件が起き、住民が世界各地に飛ばされました（小説 3 巻）。

※ この回答の数値の一部は、未確認のサンプルデータに基づいています。

※ 設定は記憶をもとに書いた非公式の下書き資料に基づき、誤りを含むことがあります。地図の日数は自作の目安です。
```

### 6. 房贷领域包（`--domain mortgage`）

比较等额本息（元利均等）与等额本金（元金均等），并计算部分提前还款（缩短期限型、减少月供型）的效果。计算由领域包内的 Python MCP 服务器
（`domains/mortgage/calc`）完成，不需要 Java。**这只是计算示例，不构成金融建议。**回答末尾必定附上这一注记。

```bash
.venv/bin/python -m core.agent "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？" \
  --domain mortgage --llm scripted --script domains/mortgage/examples/compare_methods.yaml
```

```text
利息の合計は元金均等返済の方が少なくなります。
- 元利均等返済：毎月 91,855 円、利息の合計 8,579,239 円
- 元金均等返済：初回 108,929 円から最終回 71,518 円まで減り、利息の合計 7,893,750 円
- 差：685,489 円（元利均等の方が多い）

元金均等返済は返済の初めの負担が大きいので、毎月の返済額の上限と合わせて考えてください。

※ この回答は単純なモデルによる計算例であり、金融上の助言ではありません。実際の返済額は金融機関にご確認ください。
```

（出处表从略。）加上 `--fake-backend` 时，由测试用的参考实现代替领域包的 MCP 服务器进行计算。

### 7. 网页界面（回放・评估看板・本机运行界面）

可以在网页上逐步回放执行轨迹，并查看评估看板（M5、ADR-0011）。
公开网站只有静态文件，不运行服务器和 LLM（零费用）。已公开：<https://echolab-web.echolab-web.workers.dev/>（Cloudflare（Workers 静态资源），设置见 [web/README.zh-CN.md](web/README.zh-CN.md)）。
在本机运行时，同一界面多出「运行」标签页，可以用剧本演示或真实 Claude 提问（只监听 `127.0.0.1`）。

```bash
.venv/bin/python -m servers.web_api.export && (cd web && npm ci && npm run build)
.venv/bin/python -m servers.web_api        # → http://127.0.0.1:8765/
```

### 评估与测试

```bash
.venv/bin/python -m core.evals                       # 数值忠实度（脚本模式，无需 API 密钥）
.venv/bin/python -m core.evals --cases evals/redteam/cases.yaml           # 注入评估（攻击必须无一成功）
.venv/bin/python -m core.evals --cases evals/faithfulness/mushoku.yaml    # 无职转生领域包
.venv/bin/python -m core.evals --cases evals/redteam/spoilers.yaml        # 诱导剧透的评估（无职转生）
.venv/bin/python -m core.evals --cases evals/faithfulness/mortgage.yaml   # 房贷领域包
.venv/bin/python -m core.evals --llm anthropic --out evals/reports/<名称>.md   # 真实 LLM（在本地手动运行）
.venv/bin/ruff check . && .venv/bin/pytest -m "not e2e"
```

Java 的测试、静态分析、覆盖率，以及端到端测试（`pytest -m e2e`）的运行方法见
[services/calc-engine/README.zh-CN.md](services/calc-engine/README.zh-CN.md) 与 [tests/README.zh-CN.md](tests/README.zh-CN.md)。
也可以不安装 JDK，只用 Docker 构建和测试 Java。

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check
```

## 目录结构

```
core/          领域无关的核心（Python）：契约・网关・比较工具・验证器・Agent 与 CLI・追踪・评估
config/        工具服务的启动方式（services.yaml）・成本上限与价格表（budget.yaml）
domains/wuwa/      领域包：鸣潮（domain.yaml・黄金用例・示例数据・提示词・截图模板）
domains/mushoku/   领域包：无职转生设定考证（防剧透的检索・时间线・行程，未确认的草稿资料）
domains/mortgage/  领域包：房贷还款计算示例（domain.yaml・计算与 MCP 服务器・黄金用例・提示词）
services/      calc-engine（Java 21。计算库与 MCP 服务器）
servers/       vision_mcp（截图 OCR。Python 的 MCP 服务器）・web_api（网页界面的数据导出与本机 API）
web/           网页界面（React + TypeScript + Vite）：回放・评估看板・本机运行界面
evals/         评估用例（faithfulness/）与汇总报告（reports/）
tests/         跨仓库的测试（Schema 检查・参考实现・core 单元测试・端到端测试）
docs/          架构与 ADR
```

仓库中只放已实现的部分。今后的目录在实现时再创建，计划只写在
[docs/architecture.zh-CN.md 的路线图一节](docs/architecture.zh-CN.md#路线图与今后的结构)中（ADR-0007）。
M2 的组件与契约见 ADR-0008，M3 的房贷领域包与"核心零改动"检查见 ADR-0009，M4 的截图读取与注入评估见 ADR-0010，M5 的网页界面与公开方针见 ADR-0011，M6 的无职转生领域包与防剧透见 ADR-0012。
详情请参阅 [docs/architecture.zh-CN.md](docs/architecture.zh-CN.md) 与 [docs/adr/zh-CN/](docs/adr/zh-CN/) 中的 ADR。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| M1 | Java calc-engine・黄金用例・CI | ✅ 完成 |
| M2 | 纵向切片：在 CLI 中实现"提问 → 网关（许可列表・Schema・成本上限）→ calc-engine（MCP）→ 数值追踪验证器・比较工具 → 附带出处的回答"。数值忠实度评估・执行追踪 | ✅ 完成 |
| M3 | 领域包②：房贷还款计算示例（最小示例・Python MCP 服务器）。在 CI 中检查"核心差异为零" | ✅ 完成 |
| M4 | 截图读取（OCR）・注入评估集（以脚本模式加入 CI，真实 LLM 在本地运行） | ✅ 完成 |
| M5 | 网页界面・执行轨迹回放・评估看板・公开演示（静态、零费用） | ✅ 完成（[已公开](https://echolab-web.echolab-web.workers.dev/)） |
| M6 | 领域包③：无职转生设定考证（防剧透的检索・时间线・行程）。资料是未确认的草稿 | ✅ 已实现（资料由用户核对） |

该顺序的理由见 ADR-0007（在横向扩展功能之前，先打通端到端）。

## 关于数据

`domains/wuwa/data` 中的数值是手工整理的**示例值**，`verified: false` 的条目为未确认。
在回答中使用由未确认数据计算出的数值时，必定加以注明（ADR-0006）。
黄金用例的设计使期望值只由明确给出的输入值决定，不依赖游戏的官方数值。
计算公式（防御、抗性乘区等）也是通用模型，未与游戏的实际公式核对。

无职转生领域包的资料（事实・人物・年表・地图）是凭记忆写的**未确认草稿**（`verified: false`），
使用这些资料的回答会附注记。不包含原作正文・台词・插图・影像。

房贷领域包不带数据，所有输入都由用户给出。它是固定利率、按月还款的简单模型，给出不舍入到日元的理论值。
**这只是计算示例，不构成金融建议**（回答中也必定注明）。

## 许可证

代码采用 [MIT License](LICENSE)。与游戏及作品相关的权利归各权利人所有（[免责声明](DISCLAIMER.zh-CN.md)）。
