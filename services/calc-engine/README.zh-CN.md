# calc-engine — 计算服务（Java 21）

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

*本文为译文，以日文版为准。*

负责鸣潮领域的确定性计算。**LLM 在回答中只使用这里计算出的值**（ADR-0001）。

## M1 的范围

| 包 | 内容 |
|---|---|
| `domain` | 基于 `record` 与 `sealed interface` 的模型（词条、声骸、属性）。精度策略集中在 `Precision`（`BigDecimal`、DECIMAL64） |
| `damage` | 期望伤害。以明细形式返回每个乘区的值（用于回答的数值追踪） |
| `echo` | 声骸副词条的加权评分。用 `switch` 穷举 sealed 类型 |
| `gacha` | 保底模型。精确解（马尔可夫链）与蒙特卡洛法（顺序、parallel stream、虚拟线程） |
| `golden` | 读取黄金用例（`domains/wuwa/golden/*.yaml`） |

M1 中将其构建为不依赖 Spring 的纯库，先确保计算的正确性（ADR-0004）。该方针在 M2 中不变，`dev.echolab.calc` 通过 ArchUnit 保持与框架无关。

## M2：MCP 服务器（`dev.echolab.app`）

供 Python 核心（网关）通过 MCP stdio 调用的公开层（ADR-0008）。
以 Spring Boot 4.1 + Spring AI 2.0 的 MCP 服务器（`spring-ai-starter-mcp-server`，同步、stdio）运行，只调用 `calc` 的公开 API，自身不包含计算公式。

| 包 | 内容 |
|---|---|
| `app` | 启动类・工具注册（`McpToolConfiguration`）・向 MCP 的转换（`McpToolAdapter`） |
| `app.tool` | 4 个工具的实现。输入校验（日文消息）与结果 JSON。既不依赖 Spring，也不依赖 MCP SDK |
| `app.data` | 读取 `domains/wuwa` 的数据（抽卡规则、声骸权重） |

### 工具

MCP 中的名称是将领域工具名中的 `.` 替换为 `_`（因为 Claude API 的工具名不能使用 `.`）。
输入的形式与黄金用例（`domains/wuwa/golden/*.yaml`）的 `input` 相同，黄金用例的输入可直接传入。

| MCP 名称 | 领域工具名 | 结果的 `values` |
|---|---|---|
| `damage_expected` | `damage.expected` | `base`・`bonus_multiplier`・`crit_multiplier`・`defense_multiplier`・`resistance_multiplier`・`total` |
| `echo_score` | `echo.score` | `score`・`percent_of_ideal` |
| `gacha_probability_within` | `gacha.probability_within` | `probability`（精确解） |
| `gacha_simulate` | `gacha.simulate` | `probability`・`std_error`（蒙特卡洛法。`trials` 1〜1,000,000・`seed`・`method` = `sequential`／`parallel_stream`／`virtual_threads`） |

输入 Schema（用日文说明各字段的含义、单位与范围）位于 `src/main/resources/tools/*.schema.json`。

### 数据引用

可以指定数据 ID 来代替直接给出值。两者只能指定其一（同时指定或都不指定均为错误）。

| 工具 | 直接指定 | 数据引用 |
|---|---|---|
| `gacha_probability_within`・`gacha_simulate` | `rules` | `banner`（`gacha_rules.yaml` 的 `banners[].id`） |
| `echo_score` | `weights` | `profile`（`echo_weights.yaml` 的 `profiles[].id`） |

`echo_score` 省略 `max_roll` 时，使用 `echo_weights.yaml` 中的 `max_roll`。

数据位置为 `$ECHOLAB_DATA_ROOT/wuwa/` + `domain.yaml` 的 `data_dir`（环境变量默认为相对工作目录的 `domains`）。版本目录名没有写死在代码中。

### 结果

以文本内容返回一个 JSON（对应 Python 侧 `core/contracts.py` 中的 `ToolEnvelope`）。

```json
{"tool": "gacha.probability_within",
 "values": {"probability": "0.6058637851964593"},
 "unverified_inputs": ["gacha_rules:featured-character"],
 "data_version": "v2.x"}
```

- `values` 为十进制字符串。`BigDecimal` 的结果按 `Precision` 的输出精度（小数 6 位）舍入，概率（`double`）使用最短的十进制表示。
- `unverified_inputs` 是计算中使用的未确认数据（`verified: false`）的 ID（`<数据文件名>:<条目 ID>`，例如 `echo_weights:max_roll`）。已排序且无重复（ADR-0006）。
- `data_version` 为 `domain.yaml` 的 `data_version`。未引用数据时为 `null`。
- 输入错误（缺少必填项、超出范围、未知字段、未知 ID、同时指定两者）会返回 `isError: true` 的结果，并用日文说明哪个字段有问题。服务器不会停止。MCP SDK 自带的（英文）Schema 校验已关闭，相同的条件在工具侧校验。

### stdio 注意事项

标准输出专用于 MCP 协议。不输出启动横幅（`spring.main.banner-mode=off`），不启动 Web 服务器（`spring.main.web-application-type=none`），日志通过 `logback-spring.xml` 只输出到标准错误。

## 测试

| 类型 | 内容 |
|---|---|
| 单元测试（JUnit 5） | 边界值・输入校验 |
| 性质测试（jqwik） | 概率在 [0, 1] 内・对抽数单调・硬保底必出最高稀有度・对攻击力单调 等 |
| 契约测试 | 核对 `domains/wuwa/golden/*.yaml` 的全部用例。同一文件也由 Python 参考实现核对 |
| 架构（ArchUnit） | `domain` 不依赖计算包・`calc` 不依赖 Spring、MCP SDK 与 `app`・`app.tool`／`app.data` 不依赖框架・无循环依赖 |
| MCP 层 | 将黄金用例的输入传给 MCP 工具（经由适配器）并核对（`gacha` 也用蒙特卡洛法核对）・数据引用与 `unverified_inputs`・非法输入的错误・结果 JSON 的形式 |
| 一致性 | 蒙特卡洛法的 3 种方式在相同 seed 下完全一致・与精确解在误差范围内一致 |

质量门禁：Spotless（google-java-format）、Error Prone（警告视为错误）、JaCoCo（行覆盖率低于 90% 时失败）。
唯一排除在覆盖率之外的是 Spring Boot 的启动类（`McpServerApplication`）。由于它会启动 stdio 服务器，单元测试中不启动它，而是通过以 stdio 启动 jar 的端到端测试来确认。

## 运行

无需在主机上安装 JDK，可用 Docker 运行。

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check        # 测试・格式化・静态分析・覆盖率
# 基准测试（3 种方式的速度比较）
#   ... gradle:8-jdk21 ./gradlew jmh
```

如果本地有 JDK 21，只需 `./gradlew check` 即可。

### MCP 服务器

```bash
cd services/calc-engine
./gradlew bootJar                      # 生成 build/libs/calc-engine-mcp.jar
cd ../..                               # 在仓库根目录启动（与 config/services.yaml 相同）
ECHOLAB_DATA_ROOT=domains java -jar services/calc-engine/build/libs/calc-engine-mcp.jar
```

它通过标准输入输出使用 MCP（JSON-RPC）通信，通常由 Python 核心（`core/gateway/mcp_backend.py`）按 `config/services.yaml` 的设置作为子进程启动。
`./gradlew jar` 还会生成不含 Spring Boot 的普通 jar（`build/libs/calc-engine-<版本>.jar`）。

## 已知限制

- `domains/wuwa/data/v2.x` 中的数值是**未确认的示例**（`verified: false`）。计算公式为通用模型，请在确认游戏的实际公式与常数后再提供。
- 防御与抗性乘区是通用模型。若游戏的公式不同，可替换乘区函数（每个乘区都做成独立函数正是为此）。
