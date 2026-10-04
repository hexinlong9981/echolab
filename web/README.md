# web/ — リプレイ・評価のダッシュボード・手元の実行画面

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

React + TypeScript + Vite の Web UI です（M5・[ADR-0011](../docs/adr/0011-Web-UIと公開の方針.md)）。**費用ゼロ**を最優先にしています。

| 画面 | 公開サイト | 手元 | 内容 |
|---|---|---|---|
| リプレイ | ✅ | ✅ | 実行トレースを 1 コマずつ再生する。処理の流れの図（React Flow）で、どの箱を通ったか・差し戻し・拒否を色で示し、その時点の出典の表を出す。URL `#replay/<キー>/<コマ>`（キーはデモの ID か「評価の ID-ケースの ID」。公開し直しても変わらない。例 demo-compare-builds） で特定の場面を開ける |
| 評価 | ✅ | ✅ | 鳴潮・無職転生・住宅ローンの評価（数値の忠実度・注入・ネタバレの誘導）の指標・ケースごとの結果。各ケースからリプレイへ |
| 実行（手元） | — | ✅ | 台本のデモ、または実物の Claude（API キーがあるとき、コストの上限つき）で質問し、その場でリプレイする |

公開サイトは静的なファイルだけです（サーバも LLM も動かさないので、費用がかからず、他人に API を使われる心配もありません）。
リプレイのデータは CI が台本モード（API キー不要・試験用の計算サービス）で書き出したもので、実物の LLM の応答ではありません。

## 言語（日本語・英語・中国語）

画面右上で切り替えます。最初の言語は、URL の `?lang=ja|en|zh`、前回の選択（ブラウザに保存）、ブラウザの言語の順で決まります。
日本語では、漢字に赤字のふりがな、カタカナに元の英単語を付けます（「ふりがな」「英語」のボタンで消せます）。
記録の中身（質問・回答・検証器の指摘・エラー）はプログラムの実際の出力なので、翻訳もルビもしません。

- 文言：`src/locales/{ja,en,zh}.json`、データの表示名の英中訳：`src/locales/titles.{en,zh}.json`
- 日本語のルビ：`src/locales/ja.ruby.json`。非公開リポジトリのツールで生成し、出力だけをコミットします。
  `ja.json` やデータの表示名（デモ・評価のケースの title）を変えたら生成し直してください。古いままだと Vitest（`src/i18n.test.ts`）が失敗します。

## 手元で動かす

```bash
# 1. データ（台本モードで全デモ・全評価を実行して JSON にする）
.venv/bin/python -m servers.web_api.export          # → web/public/data/（Git の管理外）
# 2. ビルド
(cd web && npm ci && npm run build)                 # → web/dist/
# 3. 手元の API（127.0.0.1 だけ）。web/dist も配るので、ブラウザで開く
.venv/bin/python -m servers.web_api                 # → http://127.0.0.1:8765/
```

開発中は `(cd web && npm run dev)`（http://127.0.0.1:5173/、`/api` は 8765 番へ中継）を使います。
`npm run typecheck`・`npm test`（Vitest）は CI でも実行します。

手元の API は、ほかのサイトのページから呼ばれないよう `Content-Type: application/json` を必須にし、`Origin` を確かめます。
台本は決まったデモのものしか使えず、任意のファイルは読めません。

## Cloudflare への公開

公開中：**<https://echolab-web.echolab-web.workers.dev/>**

Cloudflare は Workers に統合されたため、`web/dist` を Workers の**静的アセット**として公開します（`web/wrangler.jsonc`。Worker のコードは無く、無料プランの範囲）。
CI（`.github/workflows/web.yml`）は main への push のたびにビルドし、次の 2 つの Secrets があれば `wrangler deploy` で公開します。無ければ公開だけ飛ばします。

| Secret | 状態・作り方 |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | 登録済み。アカウント ID は、ダッシュボードの URL（`https://dash.cloudflare.com/<32 桁の英数字>/…`）か `npx wrangler whoami` で分かる |
| `CLOUDFLARE_API_TOKEN` | <https://dash.cloudflare.com/profile/api-tokens> →「Create Token」→ テンプレート「Edit Cloudflare Workers」の「Use template」→「Continue to summary」→「Create Token」。表示されたトークン（1 回しか表示されない）を `gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab` で登録する |

手元から公開するとき（`npx wrangler login` でログイン済みなら API トークンは要らない）：

```bash
.venv/bin/python -m servers.web_api.export && (cd web && npm run build && npx wrangler@4 deploy)
```

静的アセットへのリクエストは Workers の無料プランで無料です。ビルドは GitHub Actions で行うので、Cloudflare 側のビルドは使いません。
トークンが要らなくなったら、Cloudflare の画面で無効にしてください。

## 公開のデモサーバ（Hugging Face Spaces、ADR-0013）

デモのリプレイの下の「サーバで実際に実行」は、公開のデモサーバでそのデモを**実物の計算サービス**（Java の calc-engine・OCR・無職転生・住宅ローン）と**台本の LLM** で実行します。
実物の Claude は使わないので費用はかかりません。サーバは `python -m servers.web_api --public`（`servers/web_api/public.py`）で、像は `deploy/hf/Dockerfile` です。

手元で試す：

```bash
docker build -f deploy/hf/Dockerfile -t echolab-public .
docker run --rm -p 7860:7860 echolab-public            # → http://127.0.0.1:7860/api/health
```

公開の手順（最初の 1 回だけ）：

1. <https://huggingface.co/join> でアカウントを作る（無料・クレジットカード不要）。
2. <https://huggingface.co/new-space> で Space を作る：名前 `echolab`、SDK は **Docker**（Blank）、ハードウェアは **CPU basic（無料）**、公開範囲は **Public**（画面からログインなしで呼ぶため）。
3. 書き込み用のトークンを作る：<https://huggingface.co/settings/tokens> →「Create new token」→「Fine-grained」→「Repositories permissions」でこの Space を選び **Write** にする（作った直後に 1 回だけ表示される値を控える）。
4. **自分の端末**（Windows Terminal の WSL など。Claude Code の `!` は入力を受け取れない）で登録する：
   ```bash
   gh secret set HF_TOKEN -R hexinlong9981/echolab                                   # トークンを貼り付けて Enter
   gh variable set HF_SPACE -R hexinlong9981/echolab --body "<ユーザ名>/echolab"
   gh variable set LIVE_API_URL -R hexinlong9981/echolab --body "https://<ユーザ名>-echolab.hf.space"
   ```
5. GitHub の「Actions」→「hf-space」→「Run workflow」で Space に送る（初回の像の作成に数分）。続けて「web」を実行すると、画面に「サーバで実際に実行」が出る。

無料の CPU は使われないと休止し、次の呼び出しで起動します（画面は「起動を待っています」と表示します）。

## 構成

| 場所 | 内容 |
|---|---|
| `src/replay.ts` | トレースの出来事 → リプレイのコマ（光らせる箱・矢印・出典）。React に依存しない純粋な関数（`replay.test.ts`） |
| `src/FlowDiagram.tsx`・`src/FloatingEdge.tsx` | 処理の流れの図。矢印は箱の枠どうしを結ぶ直線 |
| `src/RunPlayer.tsx` | 1 回の実行のリプレイ（コマ送り・自動再生・出典の表・回答） |
| `src/ReplayView.tsx`・`src/EvalsView.tsx`・`src/LiveView.tsx` | 3 つの画面 |
| `../servers/web_api/` | データの書き出し（`export.py`）と手元の API（`server.py`）。Python の標準ライブラリだけ |
