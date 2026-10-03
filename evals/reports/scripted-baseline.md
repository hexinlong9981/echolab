# 評価レポート：数値の忠実度

- 日付（UTC）: 2026-10-03
- ドメイン: `wuwa`
- LLM: `scripted`
- ケース: `evals/faithfulness/cases.yaml`（8 件）

## 指標

| 指標 | 値 |
|---|---|
| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |
| 差し戻し率（差し戻した下書き / 下書き） | 0.462（6 / 13） |
| 合格したケース | 8 / 8 |
| 拒んだツール呼び出し（入力の誤り・許可外のツールなど） | 1 |
| 費用の合計（USD） | 0.028120 |

## ケースごとの結果

| ケース | 内容 | 状態 | 下書き | 差し戻し | 引用した出典 | 合否 |
|---|---|---|---|---|---|---|
| `damage-basic` | 期待ダメージと明細の引用 | answered | 1 | 0 | `c1.total`, `c1.base`, `c1.bonus_multiplier`, `c1.crit_multiplier`, `c1.defense_multiplier`, `c1.resistance_multiplier` | 合格 |
| `echo-score` | 声骸スコアの引用（値と百分率） | answered | 1 | 0 | `c1.score`, `c1.percent_of_ideal` | 合格 |
| `gacha-unverified` | 未確認データ由来の値には注記が付く | answered | 1 | 0 | `c1.probability` | 合格 |
| `compare-builds` | 並列の計算と比較ツール（差・増加率） | answered | 1 | 0 | `c1.total`, `c2.total`, `c3.diff`, `c4.change` | 合格 |
| `tool-error-recovery` | ツールの入力の誤りを読んで呼び直す | answered | 1 | 0 | `c2.probability` | 合格 |
| `bad-draft-raw-number` | 数字を直接書いた下書きは差し戻され、引用に直される | answered | 2 | 1 | `c1.total` | 合格 |
| `bad-draft-derived-and-unknown-id` | 自分で計算した差と、存在しない出典 ID は差し戻される | answered | 3 | 2 | `c1.score`, `c2.score`, `c3.diff` | 合格 |
| `never-corrected` | 差し戻しても直らなければ、数値を含まない回答に落とす | fallback | 3 | 3 | - | 合格 |

台本モードの使用量（トークン数）は台本に書いた架空の値で、費用は計算の確認用です。
