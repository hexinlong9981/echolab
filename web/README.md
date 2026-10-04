# web/ — 回放・評価のダッシュボード・手元の実行画面

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

React + TypeScript + Vite の Web UI です（M5・[ADR-0011](../docs/adr/0011-Web-UIと公開の方針.md)）。**費用ゼロ**を最優先にしています。

| 画面 | 公開サイト | 手元 | 内容 |
|---|---|---|---|
| 回放 | ✅ | ✅ | 実行トレースを 1 コマずつ再生する。処理の流れの図（React Flow）で、どの箱を通ったか・差し戻し・拒否を色で示し、その時点の出典の表を出す。URL `#replay/<実行 ID>/<コマ>` で特定の場面を開ける |
| 評価 | ✅ | ✅ | 数値の忠実度（鳴潮・住宅ローン）と注入の評価の指標・ケースごとの結果。各ケースから回放へ |
| 実行（手元） | — | ✅ | 台本のデモ、または実物の Claude（API キーがあるとき、コストの上限つき）で質問し、その場で回放する |

公開サイトは静的なファイルだけです（サーバも LLM も動かさないので、費用がかからず、他人に API を使われる心配もありません）。
回放のデータは CI が台本モード（API キー不要・試験用の計算サービス）で書き出したもので、実物の LLM の応答ではありません。

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

## Cloudflare Pages への公開（最初の 1 回だけ、手作業）

CI（`.github/workflows/web.yml`）は main への push のたびにビルドし、次の 2 つの Secrets があれば公開します。無ければ公開だけ飛ばします。

1. <https://dash.cloudflare.com/sign-up> で Cloudflare のアカウントを作る（無料・クレジットカード不要）。
2. **アカウント ID** を控える：ダッシュボードの「Workers & Pages」の画面右側、または「Account home」でアカウントの「…」→「Copy account ID」。
3. **API トークン**を作る：右上のプロフィール →「My Profile」→「API Tokens」→「Create Token」→「Create Custom Token」。
   - Permissions：`Account` ・ `Cloudflare Pages` ・ `Edit`（これ 1 つだけ）
   - Account Resources：`Include` ・ 自分のアカウント
   - 作成後に表示されるトークンを控える（1 回しか表示されません）。
4. GitHub のリポジトリに Secrets を登録する：「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で
   `CLOUDFLARE_API_TOKEN` と `CLOUDFLARE_ACCOUNT_ID`。コマンドなら：
   ```bash
   gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab     # 貼り付けて Enter
   gh secret set CLOUDFLARE_ACCOUNT_ID -R hexinlong9981/echolab
   ```
5. 「Actions」→「web」→「Run workflow」で実行する（または次の push を待つ）。初回はプロジェクト `echolab` を作ってから公開します。
   URL は `https://echolab.pages.dev/`（名前が使われていれば Cloudflare が別名を付けます。ダッシュボードで確認できます）。

Cloudflare Pages の無料プランの範囲（帯域は無制限、ビルドは月 500 回まで。ビルドは GitHub Actions で行うので、Cloudflare 側のビルドは使いません）で動きます。
トークンの権限は Pages の編集だけなので、漏れてもほかの設定は変えられません。不要になったら Cloudflare の画面で無効にしてください。

## 構成

| 場所 | 内容 |
|---|---|
| `src/replay.ts` | トレースの出来事 → 回放のコマ（光らせる箱・矢印・出典）。React に依存しない純粋な関数（`replay.test.ts`） |
| `src/FlowDiagram.tsx`・`src/FloatingEdge.tsx` | 処理の流れの図。矢印は箱の枠どうしを結ぶ直線 |
| `src/RunPlayer.tsx` | 1 回の実行の回放（コマ送り・自動再生・出典の表・回答） |
| `src/ReplayView.tsx`・`src/EvalsView.tsx`・`src/LiveView.tsx` | 3 つの画面 |
| `../servers/web_api/` | データの書き出し（`export.py`）と手元の API（`server.py`）。Python の標準ライブラリだけ |
