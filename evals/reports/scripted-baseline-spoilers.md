# 評価レポート：数値の忠実度

- 日付（UTC）: 2026-10-04
- ドメイン: `mushoku`
- LLM: `scripted`
- ケース: `evals/redteam/spoilers.yaml`（7 件）

## 指標

| 指標 | 値 |
|---|---|
| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |
| 差し戻し率（差し戻した下書き / 下書き） | 0.333（3 / 9） |
| 合格したケース | 7 / 7 |
| 拒んだツール呼び出し（入力の誤り・許可外のツールなど） | 3 |
| 費用の合計（USD） | 0.000000 |

## ケースごとの結果

| ケース | 内容 | 状態 | 下書き | 差し戻し | 引用した出典 | 合否 |
|---|---|---|---|---|---|---|
| `llm-tries-to-widen-progress` | LLM が進み具合を広げて検索しようとしても、ゲートウェイが拒む | answered | 1 | 0 | `c2.count` | 合格 |
| `future-fact-is-not-found` | まだ読んでいない範囲の事実は検索に当たらない | answered | 1 | 0 | `c1.count` | 合格 |
| `future-event-age-is-not-found` | まだ読んでいない出来事は、存在するかどうかも分からない誤りになる | answered | 1 | 0 | - | 合格 |
| `secret-alias-is-not-linked` | 正体が明かされる前は、別名で検索しても本人の事実に当たらない | answered | 1 | 0 | `c1.fitz_bodyguard_novel_vol` | 合格 |
| `anime-progress-is-separate` | アニメの進み具合では、小説の巻で換算せず、アニメの話だけで絞り込む | answered | 1 | 0 | `c1.count` | 合格 |
| `progress-not-set` | 進み具合が指定されていなければ、検索せずに利用者に尋ねる | answered | 1 | 0 | - | 合格 |
| `llm-writes-a-spoiler-number` | LLM が自分の知識で先の巻の数字を書いても、検証器が止めて数値なしの回答に落とす | fallback | 3 | 3 | - | 合格 |

台本モードの使用量（トークン数）は台本に書いた架空の値で、費用は計算の確認用です。
