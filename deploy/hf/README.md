---
title: EchoLab demo server
emoji: 🧮
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Runs EchoLab's fixed demos live with real calc services
---

# EchoLab の公開デモサーバ

[EchoLab](https://github.com/hexinlong9981/echolab)（AI に計算させない AI アシスタント）の決まったデモを、
実物の計算サービス（Java の calc-engine・OCR・住宅ローン・無職転生）で実行して返すサーバです（ADR-0013）。

- LLM は台本だけを使います（実物の Claude は使わず、API キーもありません。費用はかかりません）。
- 画面は <https://echolab-web.echolab-web.workers.dev/> から使います。この Space の API は `GET /api/health`・`POST /api/ask`。
- 同時に 1 件、接続元ごとに 1 分 6 回・1 日 60 回まで。しばらく使われないと休止し、次の呼び出しで起動します（1 分ほどかかります）。

このファイルと Space の中身は、公開リポジトリの `deploy/hf/` から CI が自動で送ります。直接編集しないでください。

---

**English**: A server that runs EchoLab's fixed demos live with the real calc services (Java calc-engine, OCR, Mushoku Tensei, mortgage) and the scripted LLM only — no real Claude, no API key, no cost. Use it from <https://echolab-web.echolab-web.workers.dev/>. Deployed automatically from the public repo's `deploy/hf/`.

**中文**：用真实计算服务（Java calc-engine・OCR・无职转生・房贷）和剧本 LLM 现场运行 EchoLab 固定演示的服务器，不使用真实 Claude、没有 API 密钥、没有费用。请从 <https://echolab-web.echolab-web.workers.dev/> 使用。由公开仓库的 `deploy/hf/` 自动部署。
