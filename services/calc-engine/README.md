# calc-engine — 計算サービス（Java 21）

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

鳴潮ドメインの決定的な計算を担当します。**LLM はここで計算した値だけを回答に使います**（ADR-0001）。

## M1 の範囲

| パッケージ | 内容 |
|---|---|
| `domain` | `record` と `sealed interface` によるモデル（詞条・声骸・ステータス）。精度方針は `Precision` に集約（`BigDecimal`・DECIMAL64） |
| `damage` | 期待ダメージ。乗区ごとの値を明細として返す（回答の数値トレースに使う） |
| `echo` | 声骸サブ詞条の重み付きスコア。`switch` による sealed 型の網羅 |
| `gacha` | 天井モデル。厳密解（マルコフ連鎖）とモンテカルロ法（逐次・parallel stream・仮想スレッド） |
| `golden` | ゴールデンケース（`domains/wuwa/golden/*.yaml`）の読み込み |

M1 では Spring に依存しない純粋なライブラリとして作り、計算の正しさを先に固めました（ADR-0004）。この方針は M2 でも変わらず、`dev.echolab.calc` は ArchUnit でフレームワーク非依存に保っています。

## M2：MCP サーバ（`dev.echolab.app`）

Python のコア（ゲートウェイ）から MCP の stdio で呼ぶための公開層です（ADR-0008）。
Spring Boot 4.1 + Spring AI 2.0 の MCP サーバ（`spring-ai-starter-mcp-server`、同期・stdio）で動き、`calc` の公開 API を呼ぶだけで計算式は持ちません。

| パッケージ | 内容 |
|---|---|
| `app` | 起動クラス・ツールの登録（`McpToolConfiguration`）・MCP への変換（`McpToolAdapter`） |
| `app.tool` | ツール 4 つの中身。入力の検証（日本語のメッセージ）と結果の JSON。Spring にも MCP の SDK にも依存しない |
| `app.data` | `domains/wuwa` のデータ（ガチャ規則・声骸の重み）の読み込み |

### ツール

MCP での名前は、ドメインのツール名の `.` を `_` に替えたものです（Claude API のツール名に `.` を使えないため）。
入力の形はゴールデンケース（`domains/wuwa/golden/*.yaml`）の `input` と同じで、ゴールデンケースの入力はそのまま渡せます。

| MCP の名前 | ドメインのツール名 | 結果の `values` |
|---|---|---|
| `damage_expected` | `damage.expected` | `base`・`bonus_multiplier`・`crit_multiplier`・`defense_multiplier`・`resistance_multiplier`・`total` |
| `echo_score` | `echo.score` | `score`・`percent_of_ideal` |
| `gacha_probability_within` | `gacha.probability_within` | `probability`（厳密解） |
| `gacha_simulate` | `gacha.simulate` | `probability`・`std_error`（モンテカルロ法。`trials` 1〜1,000,000・`seed`・`method` = `sequential`／`parallel_stream`／`virtual_threads`） |

入力スキーマ（各フィールドの意味・単位・範囲を日本語で説明）は `src/main/resources/tools/*.schema.json` にあります。

### データの参照

値を直接与える代わりに、データの ID を指定できます。どちらか一方だけを指定します（両方・どちらも無しはエラー）。

| ツール | 直接指定 | データの参照 |
|---|---|---|
| `gacha_probability_within`・`gacha_simulate` | `rules` | `banner`（`gacha_rules.yaml` の `banners[].id`） |
| `echo_score` | `weights` | `profile`（`echo_weights.yaml` の `profiles[].id`） |

`echo_score` は `max_roll` を省略すると `echo_weights.yaml` の `max_roll` を使います。

データの場所は `$ECHOLAB_DATA_ROOT/wuwa/` + `domain.yaml` の `data_dir` です（環境変数の既定は作業ディレクトリからの `domains`）。版のディレクトリ名はコードに書いていません。

### 結果

テキスト内容に JSON を 1 つ返します（Python 側の `core/contracts.py` の `ToolEnvelope`）。

```json
{"tool": "gacha.probability_within",
 "values": {"probability": "0.6058637851964593"},
 "unverified_inputs": ["gacha_rules:featured-character"],
 "data_version": "v2.x"}
```

- `values` は 10 進数の文字列です。`BigDecimal` の結果は `Precision` の出力桁（小数 6 桁）に丸め、確率（`double`）は最短の 10 進表現にします。
- `unverified_inputs` は計算に使った未確認データ（`verified: false`）の ID（`<データファイル名>:<項目 ID>`、例 `echo_weights:max_roll`）です。整列済みで重複はありません（ADR-0006）。
- `data_version` は `domain.yaml` の `data_version` です。データを参照しなかった場合は `null` です。
- 入力の誤り（必須の欠落・範囲外・未知のフィールド・未知の ID・両方指定）は `isError: true` の結果になり、どのフィールドが悪いかを日本語で返します。サーバは止まりません。MCP の SDK による（英語の）スキーマ検証は切り、同じ条件をツール側で検証しています。

### stdio での注意

標準出力は MCP のプロトコル専用です。バナーは出さず（`spring.main.banner-mode=off`）、Web サーバも起動せず（`spring.main.web-application-type=none`）、ログは `logback-spring.xml` で標準エラーにだけ出します。

## テスト

| 種類 | 内容 |
|---|---|
| 単体テスト（JUnit 5） | 境界値・入力検証 |
| 性質テスト（jqwik） | 確率が [0, 1]・回数に対して単調・ハード天井で必ず最高レア・攻撃力に対して単調 など |
| 契約テスト | `domains/wuwa/golden/*.yaml` を全件照合。同じファイルを Python の参照実装でも照合している |
| アーキテクチャ（ArchUnit） | `domain` が計算パッケージに依存しない・`calc` が Spring・MCP の SDK・`app` に依存しない・`app.tool`／`app.data` がフレームワークに依存しない・循環依存がない |
| MCP 層 | ゴールデンケースの入力を MCP のツール（アダプタ経由）に渡して照合（`gacha` はモンテカルロ法でも照合）・データ参照と `unverified_inputs`・不正な入力のエラー・結果の JSON の形 |
| 一致性 | モンテカルロ法の 3 方式が同じ seed で完全一致・厳密解と誤差内で一致 |

品質ゲート: Spotless（google-java-format）、Error Prone（警告はエラー扱い）、JaCoCo（行カバレッジ 90% 未満で失敗）。
カバレッジの対象外は Spring Boot の起動クラス（`McpServerApplication`）だけです。stdio のサーバが立ち上がるため単体テストでは起動せず、jar を stdio で起動する端から端までの試験で確かめます。

## 実行

ホストに JDK を入れずに Docker で実行できます。

```bash
cd services/calc-engine
docker run --rm -u "$(id -u):$(id -g)" -e GRADLE_USER_HOME=/cache \
  -v "$HOME/.gradle-echolab:/cache" -v "$(cd ../.. && pwd):/w" -w /w/services/calc-engine \
  gradle:8-jdk21 ./gradlew check        # テスト・整形・静的解析・カバレッジ
# ベンチマーク（3 方式の速度比較）
#   ... gradle:8-jdk21 ./gradlew jmh
```

JDK 21 が手元にあれば `./gradlew check` だけで動きます。

### MCP サーバ

```bash
cd services/calc-engine
./gradlew bootJar                      # build/libs/calc-engine-mcp.jar ができる
cd ../..                               # リポジトリ直下で起動する（config/services.yaml と同じ）
ECHOLAB_DATA_ROOT=domains java -jar services/calc-engine/build/libs/calc-engine-mcp.jar
```

標準入出力で MCP（JSON-RPC）を話すので、通常は Python のコア（`core/gateway/mcp_backend.py`）が `config/services.yaml` の設定で子プロセスとして起動します。
`./gradlew jar` では Spring Boot を含まない通常の jar（`build/libs/calc-engine-<版>.jar`）もできます。

## 既知の制約

- `domains/wuwa/data/v2.x` の数値は**未確認のサンプル**です（`verified: false`）。計算式は汎用モデルで、実際のゲームの式・定数は確認してから与えてください。
- 防御・耐性の乗区は汎用モデルです。ゲームによって式が異なる場合は、乗区の関数を差し替えます（各乗区を独立した関数にしてあるのはこのためです）。
