# 評価レポート：数値の忠実度

- 日付（UTC）: 2026-10-03
- ドメイン: `mortgage`
- LLM: `scripted`
- ケース: `evals/faithfulness/mortgage.yaml`（5 件）

## 指標

| 指標 | 値 |
|---|---|
| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |
| 差し戻し率（差し戻した下書き / 下書き） | 0.500（4 / 8） |
| 合格したケース | 5 / 5 |
| 費用の合計（USD） | 0.000000 |

## ケースごとの結果

| ケース | 内容 | 状態 | 下書き | 差し戻し | 引用した出典 | 合否 |
|---|---|---|---|---|---|---|
| `compare-methods` | 元利均等と元金均等の利息の比較（並列の計算と比較ツール） | answered | 1 | 0 | `c1.monthly_payment`, `c1.total_interest`, `c2.first_payment`, `c2.last_payment`, `c2.total_interest`, `c3.diff` | 合格 |
| `prepayment-methods` | 繰上返済の 2 つの方式の比較 | answered | 1 | 0 | `c1.months_saved`, `c1.interest_saved`, `c2.monthly_payment_after`, `c2.interest_saved`, `c3.diff` | 合格 |
| `ask-for-missing-conditions` | 条件が足りなければ推測せずに尋ねる（数値を含まない回答） | answered | 1 | 0 | - | 合格 |
| `bad-draft-self-computed-diff` | 自分で引き算した差は差し戻され、比較ツールに直される | answered | 2 | 1 | `c3.diff`, `c1.total_interest`, `c2.total_interest` | 合格 |
| `never-corrected` | 差し戻しても直らなければ、数値を含まない定型の回答（注記は付けない） | fallback | 3 | 3 | - | 合格 |

台本モードの使用量（トークン数）は台本に書いた架空の値で、費用は計算の確認用です。
