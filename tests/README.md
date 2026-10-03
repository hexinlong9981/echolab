# tests/ — リポジトリ横断のテスト（Python）

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

## 契約とデータ

| ファイル | 内容 |
|---|---|
| `test_golden_schema.py` | ゴールデンケース（`domains/*/golden`・`core/golden`）とドメインデータの形式を JSON Schema で検査。`verified: false` の値には出典が TODO であることを要求。各ツールに `derivation` が `reference` 以外（手計算・閉形式）のケースが最低 1 件あることを要求。`verified: true` の出典規則（ADR-0006）が効くことを、違反例と正常例で確認 |
| `test_golden_reference.py` | ゴールデンケースの期待値を Python の参照実装（`reference/calc_reference.py`）で再計算。比較ツールのケース（`core/golden`）は `core.compare` と照合。Java の契約テストと合わせて、YAML・Java・Python の 3 者一致を保証 |
| `test_domain_manifest.py` | ドメインパックのマニフェスト（`domains/*/domain.yaml`）を `schemas/domain.schema.json` で検査。`name` とディレクトリ名の一致、`data_dir`・`golden_dir`・`prompts_dir` の存在、ゴールデンケースのツールがすべて `tools` に宣言されていること、ツール名の重複がないことを確認 |

## コア（`core/`）の単体テスト：`tests/core/`

API キーも Java も使いません。LLM は台本（`ScriptedLLM`）または SDK のクライアントの偽物、計算サービスは偽物で置き換えます。

| ファイル | 内容 |
|---|---|
| `fakes.py` | 試験用の偽の計算サービス（`FakeCalcBackend`）。Java を起動せず、参照実装で計算する。CLI の `--fake-backend` と台本モードの評価でも使う |
| `stub_mcp_server.py` | 試験用の小さな stdio の MCP サーバ。calc-engine と同じ形の結果（`ToolEnvelope` の JSON）を返す |
| `test_gateway.py` | ゲートウェイ：許可リスト（宣言の無いツール・未公開のツールは見せず、呼ばせない）・入力スキーマの検査（違反ならサービスを呼ばない）・呼び出し ID と出典 ID の採番（並行でも一意）・比較ツールの出典 ID の解決と未確認データの伝搬 |
| `test_gateway_budget.py` | コストの台帳と上限：料金表による計算・日次と月次の上限・UTC での日付と月の区切り・読めない台帳では止める・料金表に無いモデルの安全側の見積もり・環境変数による上書き |
| `test_mcp_backend.py` | `McpStdioBackend` を `stub_mcp_server.py` に対して実行：ツールの一覧と呼び出し・起動の失敗の報告・`config/services.yaml` からの起動 |
| `test_compare.py` | 比較ツール（差・比・増加率）の計算・丸め・0 での除算 |
| `test_verifier.py` | レンダラの書式（桁数・百分率・桁区切り・丸め）と、検証器の判定（プレースホルダの形式・未知の出典 ID・出典の無い数字・質問の数値の引用・許可リスト・未確認データの注記） |
| `test_agent.py` | Agent の往復：並列のツール呼び出し・ツールの誤りからの回復・差し戻しと再試行・数値を含まない回答への切り替え・コストの上限・往復の上限・拒否と出力の打ち切り・LLM の失敗 |
| `test_llm_anthropic.py` | Claude の LLM 実装：要求の組み立て（モデル・思考の深さ・フォールバック・プロンプトキャッシュ）・応答の正規化・フォールバック時の課金・拒否と API の誤り |
| `test_llm_scripted.py` | 台本の LLM：応答の順序・`expect` の照合・例の台本の読み込み |
| `test_trace.py` | 実行トレース：1 行 1 出来事の JSONL・契約の型の書き出し・Agent が残す出来事の中身 |
| `test_evals.py` | 数値の忠実度の評価を台本モードで全ケース実行し、コミット済みの `evals/reports/scripted-baseline.md` と一致することを確認 |

## ドメインパック②：住宅ローン（ADR-0009）

Java は使いません。パックの MCP サーバ（Python）は実物を子プロセスで起動するので、CI の `python` ジョブで毎回通します。

| ファイル | 内容 |
|---|---|
| `reference/mortgage_reference.py` | 住宅ローンの参照実装。パックの実装（`Decimal`、残高を 1 回ずつ進める）とは別の方法（`float`、残高の公式と対数で回数を求める）で計算する |
| `test_mortgage_pack.py` | パックの実装とゴールデンケースの照合・入力の誤りの説明・実物の MCP サーバをゲートウェイから起動してのゴールデンケースの照合とエラー・Agent の往復と回答の注記・台本モードの評価（`evals/faithfulness/mortgage.yaml`）とベースライン |
| `test_pack_isolation.py` | CI の「パックの変更でコアを変えない」検査（`.github/scripts/check_pack_isolation.py`）の規則を、一時的な git リポジトリで確かめる |

## 端から端までの試験：`tests/e2e/`

`test_mcp_e2e.py` は実物の calc-engine（MCP サーバの jar）を `config/services.yaml` のとおりに起動します。

- ゴールデンケースを MCP 経由で全件照合する（Java の単体テスト・Python の参照実装に続く 3 つ目の照合）。
- 起動直後の並列の呼び出し・不正な入力のエラー・データ参照による未確認データの伝搬と注記を確かめる。
- 台本の LLM で、Agent の往復を実物の計算サービスの上で通す。

実行には jar と JDK 21 が必要です。どちらかが無いときは飛ばします（CI では `ECHOLAB_E2E_REQUIRED=1` で、飛ばさずに失敗させます）。

```bash
(cd services/calc-engine && ./gradlew bootJar)      # build/libs/calc-engine-mcp.jar
export JAVA_HOME=/path/to/jdk-21 PATH="$JAVA_HOME/bin:$PATH"
.venv/bin/pytest -m e2e
```

CI では、`test.yml` の `python` ジョブが `pytest -m "not e2e"` を、`e2e` ジョブが jar を作ってから `pytest -m e2e` を実行します。

`pack-isolation` ジョブは、ドメインパックの変更でコアを変えていないことを git の履歴で検査します（ADR-0009）。
