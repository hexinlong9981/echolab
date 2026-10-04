# domains/mushoku — ドメインパック③：無職転生の設定考証（非公式）

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

> **非公式のファン作品です。** 『無職転生 ～異世界行ったら本気だす～』の権利は原作者・出版社・アニメの製作者などの各権利者にあります。
> 原作の本文・台詞・挿絵・アニメの画像は収録しません。収録するのは、自分で書いた短い要約と、巻・話の番号だけです。
> **資料はすべて記憶をもとに書いた未確認の下書き**（`verified: false`）で、誤りを含むことがあります。地図の日数は自作の目安です。

設定・時系列・旅程の質問に答えるパックです（M6・[ADR-0012](../../docs/adr/0012-無職転生のパックとネタバレ防止.md)）。
見どころは**ネタバレ防止**です。業務での「利用者の権限に応じて検索結果を絞る」のと同じ仕組みを、検索の層で必ず行います。

## ネタバレ防止の仕組み

- **進み具合は利用者が指定する**：`--context progress=novel:5`（小説 5 巻まで）、`--context progress=anime:2-12`（アニメ 2 期 12 話まで）。
  `progress` は `domain.yaml` の `user_context` で、ゲートウェイが LLM に見せずに入力に加えます。LLM が送ってきたら拒みます。
- **申告した媒体だけで絞り込む**：小説とアニメの間で換算しません。その媒体の注記が無い項目は返しません（既定拒否）。
- **見えない＝存在しない**：まだ読んでいない人物・出来事・場所は、資料に無いものと同じ誤りになります。
- **正体のネタバレも防ぐ**：正体が分かる別名（例：フィッツ）は、明かされる巻・話から先でだけ使います。事実のタグは、その文だけで分かることに限ります。
- **限界**：LLM が自分の知識で書いた「数字を含まないネタバレ文」は構造では止められません（プロンプトで禁じるだけ）。数字を含むものは検証器が止めます。

## ツール

| ツール | 内容 | 結果 |
|---|---|---|
| `lore.search` | キーワード（すべて含む）で事実を探す。人物・場所の名前でも当たる | `values`：件数・各事実の巻（または期・話）、`texts`：事実の文（数字を含まない） |
| `timeline.age` | 出来事の年の人物の年齢 | `age`・`birth_year`・`event_year`（甲龍歴） |
| `timeline.span` | 2 つの出来事の間の年数 | `years`・`from_year`・`to_year` |
| `map.route` | 自作の地図での最短の旅程（見えている道だけ） | `total_days`・`legs`、`texts` に道順 |

## 構成

| 場所 | 内容 |
|---|---|
| `data/draft-1/` | 事実（40）・人物（18）・出来事（3）・場所（8）と道（7）。スキーマは `schema/` |
| `service/` | 検索・時系列・旅程（`lore.py`）と MCP サーバ（`server.py`、`config/services.yaml` の `mushoku-lore`） |
| `golden/` | ゴールデンケース（手計算）。参照実装は `tests/reference/mushoku_reference.py` |
| `prompts/system.md`・`examples/` | プロンプトと台本のデモ |

```bash
.venv/bin/python -m core.agent "転移事件のとき、ルーデウスは何歳だった？" --domain mushoku \
  --context progress=novel:3 --llm scripted --script domains/mushoku/examples/teleport_age.yaml
.venv/bin/python -m core.evals --cases evals/redteam/spoilers.yaml      # ネタバレの誘導の評価（7 件）
```

資料を確かめたら、その項目を `verified: true` にし、`source` に巻・話などの具体的な箇所、`checked_at` に確認日を書きます（スキーマで必須）。
