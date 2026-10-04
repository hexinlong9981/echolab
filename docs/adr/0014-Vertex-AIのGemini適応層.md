**日本語** ｜ [English](en/0014-vertex-ai-gemini-adapter.md) ｜ [中文](zh-CN/0014-Vertex-AI的Gemini适配层.md)

# ADR-0014: Vertex AI の Gemini 適応層（実物の LLM 評価と GCP 無料枠の活用）

- 状態: 採用
- 日付: 2026-10-04

## 背景

M2（[ADR-0008](0008-M2の構成と契約.md)）で実装した実物の LLM 評価は Claude（Anthropic API）のみを対象としていた。しかし、Anthropic API は従量課金であり、クレジットカードによる事前チャージが必要となる。
一方、プロジェクトでは Google Cloud の無料試用枠（約 47,000 円分のクレジット）が利用可能であり、Vertex AI の Gemini API であれば追加の手出し費用ゼロで実物の LLM 評価を実施できる。
また、将来的にマルチプロバイダ対応を行う上でも、コアの不変条件（ADR-0008：LLM は数値を書かずツールから引用する）を異なる LLM アーキテクチャで実証することは重要である。

## 決定

| 項目 | 決定 |
|---|---|
| ライブラリ | 統合 SDK `google-genai`（v2）を採用。Vertex AI モード（`vertexai=True`）で動作させる |
| 認証 | Google Cloud の標準である Application Default Credentials（ADC）および環境変数（`GCP_PROJECT_ID`・`GCP_REGION`） |
| モデル | 既定は `gemini-2.5-flash`（低廉・高速・関数呼び出しが高精度）。`gemini-2.5-pro` も指定可能 |
| 自動関数呼び出し | 自動呼び出し（AFC）は無効化（`disable=True`）し、エージェントループがツールの認可・実行・差し戻しを一元管理する |
| 思考ブロックの扱い | Gemini 2.5 の内部推論（`thought=True`）は回答本文（`texts`）から除外し、検証器が推論過程の数値を誤って拾わないようにする。履歴（`raw_content`）には思考署名を含めて保持する |
| 料金計算 | `config/budget.yaml` に Gemini 各モデルの入力・出力・キャッシュ単価を登録し、`Budget` の日次・月次上限で監視する |
| CLI / 評価 | `--llm gemini` および `--model` オプションを追加。`core.agent` と `core.evals` の双方で指定可能 |

ドメインパックの隔離（`domains/` の非接触）を守り、`core/agent/llm/gemini.py` として独立して実装する。

## 理由

- `gemini-2.5-flash` は極めて安価（100 万トークンあたり入力 $0.075 / 出力 $0.30）であり、全 8 件の忠実度評価を実行しても約 $0.003（約 0.45 円）しかかからない。GCP の試用枠内で潤沢に評価を回せる。
- Gemini 2.5 は推論（thinking）を行うため、推論過程の数値がテキストに含まれると ADR-0008 の数値検証器が「未出典の数値」として差し戻してしまう。思考ブロックを本文から明示的に分離することで、モデルの推論能力を活かしつつ決定論的な数値引用を両立できた。
- 統合 SDK `google-genai` の非同期クライアント（`client.aio`）を使うことで、既存の `loop.py` との親和性を保ち、外部プロセス起動等のオーバーヘッドなく呼び出せる。

## 却下した案

| 案 | 却下した理由 |
|---|---|
| Claude（Anthropic API）だけで済ませる | GCP の試用クレジットが使えず、自費での API チャージが発生する（費用最優先の方針に反する） |
| Google AI Studio（API キー方式） | 試用クレジットの対象外であり、別途 API キーの管理が必要になる |
| 自動関数呼び出し（AFC）を有効にする | LLM が直接ツールを実行してしまい、ゲートウェイの既定拒否・JSON Schema 検証・出処 ID 採番・検証器の差し戻しを迂回してしまう（ADR-0008 に違反） |
| 思考ブロックを無効化（budget=0）する | モデルの理解力・ツール選択精度が低下する懸念がある。思考自体は行わせ、検証対象のテキストからのみ除外するのが最も安全 |

## 影響

- 新しいファイル：`core/agent/llm/gemini.py`、`tests/core/test_llm_gemini.py`、`evals/reports/gemini-baseline.md`。
- 変更：`requirements.txt`（`google-genai` 追加）、`config/budget.yaml`（料金表追加）、`core/agent/`・`core/evals/`（CLI 選択肢）。
- 評価：実機で `python -m core.evals --llm gemini` を実行し、全件の忠実度（1.000）と動作を確認済み。
