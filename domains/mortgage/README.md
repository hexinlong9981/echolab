# domains/mortgage — ドメインパック②：住宅ローンの返済の計算例

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

> **計算例であり、金融上の助言ではありません。** 固定金利・毎月払いの単純なモデルで、円未満を丸めない理論値を返します。
> 実際の返済額・条件は金融機関にご確認ください。回答の末尾にも必ずこの旨の注記が付きます（`domain.yaml` の `answer_note`）。

コアを 1 行も変えずに 2 つ目のドメインを足せることを示す最小例です（ADR-0003・[ADR-0009](../../docs/adr/0009-住宅ローンのパックとコアの差分ゼロ.md)）。

## ツール

| ツール | 入力 | 結果のフィールド |
|---|---|---|
| `mortgage.equal_payment`（元利均等） | `principal`（円）・`annual_rate`（小数、0.015 = 年 1.5%）・`years` | `monthly_payment`・`total_payment`・`total_interest` |
| `mortgage.equal_principal`（元金均等） | 同上 | `first_payment`・`last_payment`・`total_payment`・`total_interest` |
| `mortgage.prepayment`（一部繰上返済） | 同上 ＋ `after_months`（済ませた返済の回数）・`prepay_amount`（円）・`method`（`shorten_term` 期間短縮型／`reduce_payment` 返済額軽減型） | `balance_before`・`monthly_payment_after`・`remaining_months_after`・`total_interest_before`・`total_interest_after`・`interest_saved`・`months_saved` |

差（元利均等と元金均等の利息の差など）は、コアの比較ツール `compare.diff`・`compare.ratio` で求めます。

## 構成

| 場所 | 内容 |
|---|---|
| `domain.yaml` | パックのマニフェスト。ツール・プロンプト・回答の注記を宣言する。データは持たない |
| `calc/loan.py` | 計算。`Decimal`（有効桁 34）、出力は小数 6 桁・ROUND_HALF_EVEN。期間短縮型は残高を 1 回ずつ進め、最後の回は残りの元金と利息だけを払う |
| `calc/server.py` | MCP サーバ（stdio）。`config/services.yaml` の `mortgage-calc`（`python -m domains.mortgage.calc`）としてコアのゲートウェイが起動する |
| `calc/schemas/` | ツールの入力スキーマ（JSON Schema）。ゲートウェイが呼ぶ前に検査する |
| `golden/` | ゴールデンケース。各ツールに手計算か閉形式のケースがある |
| `prompts/system.md` | ドメインのシステムプロンプト（ツールの使い分け） |
| `examples/compare_methods.yaml` | 台本モードのデモ（API キー不要） |

## 動かす

```bash
.venv/bin/python -m core.agent "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？" \
  --domain mortgage --llm scripted --script domains/mortgage/examples/compare_methods.yaml
.venv/bin/python -m core.evals --cases evals/faithfulness/mortgage.yaml   # 台本モードの評価（5 件）
.venv/bin/pytest tests/test_mortgage_pack.py                              # 実装・MCP サーバ・評価の試験
```

## モデルに含まれないもの

円未満の端数処理、日割りの利息、ボーナス払い、変動金利・金利の見直し、手数料、税金（住宅ローン控除など）、団体信用生命保険。
