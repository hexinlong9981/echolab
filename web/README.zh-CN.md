# web/ — 回放・评估看板・本机运行界面

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

用 React + TypeScript + Vite 做的网页界面（M5、[ADR-0011](../docs/adr/zh-CN/0011-网页界面与公开方针.md)）。**零费用**是最优先的原则。

| 界面 | 公开网站 | 本机 | 内容 |
|---|---|---|---|
| 回放 | ✅ | ✅ | 逐步播放执行轨迹。用流程图（React Flow）以颜色标出经过的方框、退回和拒绝，并显示当时的出处表。用网址 `#replay/<键>/<步>`（键是演示的 ID 或「评估 ID-用例 ID」，重新发布也不变，例如 demo-compare-builds） 可以直接打开某个时刻 |
| 评估 | ✅ | ✅ | 鸣潮・无职转生・房贷的评估（数值忠实度・注入・诱导剧透）的指标和每个用例的结果，可从每个用例跳到回放 |
| 运行（本机） | — | ✅ | 用剧本演示或真实 Claude（有 API 密钥时，受成本上限保护）提问，并当场回放 |

公开网站只有静态文件（不运行服务器和 LLM，所以没有费用，也不会被别人用掉你的 API）。
回放数据是 CI 用剧本模式（无需 API 密钥、测试用计算服务）导出的，不是真实 LLM 的回答。

## 语言（日语・英语・中文）

在右上角切换。初始语言依次取决于网址的 `?lang=ja|en|zh`、上次的选择（保存在浏览器中）、浏览器的语言。
日语界面中，汉字上方标红色假名，片假名上方标英文原词（可用「ふりがな」「英語」按钮隐藏）。
记录的内容（问题・回答・验证器的指摘・错误）是程序的实际输出，不翻译也不标注。

- 文字：`src/locales/{ja,en,zh}.json`；数据显示名的英中译文：`src/locales/titles.{en,zh}.json`
- 日语注音：`src/locales/ja.ruby.json`，由非公开仓库的工具生成，只提交输出。
  修改 `ja.json` 或数据显示名（演示・评估用例的 title）后要重新生成；过时的话 Vitest（`src/i18n.test.ts`）会失败。

## 在本机运行

```bash
# 1. 数据（用剧本模式运行全部演示与评估，写成 JSON）
.venv/bin/python -m servers.web_api.export          # → web/public/data/（不纳入 Git）
# 2. 构建
(cd web && npm ci && npm run build)                 # → web/dist/
# 3. 本机 API（只监听 127.0.0.1）。它同时提供 web/dist，用浏览器打开即可
.venv/bin/python -m servers.web_api                 # → http://127.0.0.1:8765/
```

开发时用 `(cd web && npm run dev)`（http://127.0.0.1:5173/，`/api` 转发到 8765 端口）。
`npm run typecheck`・`npm test`（Vitest）在 CI 中也会运行。

为了不让其他网站的页面调用本机 API，它要求 `Content-Type: application/json` 并检查 `Origin`。
只能使用固定的演示剧本，不能读取任意文件。

## 发布到 Cloudflare

已公开：**<https://echolab-web.echolab-web.workers.dev/>**

Cloudflare 已并入 Workers，所以把 `web/dist` 作为 Workers 的**静态资源**发布（`web/wrangler.jsonc`；没有 Worker 代码，在免费方案范围内）。
CI（`.github/workflows/web.yml`）每次推送到 main 都会构建，有下面两个 Secrets 时用 `wrangler deploy` 发布；没有时只跳过发布这一步。

| Secret | 状态・创建方法 |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | 已登记。账号 ID 在后台网址（`https://dash.cloudflare.com/<32 位字母数字>/…`）中，或用 `npx wrangler whoami` 查看 |
| `CLOUDFLARE_API_TOKEN` | <https://dash.cloudflare.com/profile/api-tokens> →「Create Token」→ 模板「Edit Cloudflare Workers」的「Use template」→「Continue to summary」→「Create Token」。把显示出来的令牌（只显示一次）用 `gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab` 登记 |

从本机发布时（用 `npx wrangler login` 登录后不需要 API 令牌）：

```bash
.venv/bin/python -m servers.web_api.export && (cd web && npm run build && npx wrangler@4 deploy)
```

在 Workers 免费方案中，静态资源的请求是免费的。构建在 GitHub Actions 中完成，不使用 Cloudflare 的构建。
不再需要令牌时，请在 Cloudflare 后台作废。

## 公开的演示服务器（Google Cloud Run，ADR-0013）

演示回放下方的「在服务器上实际运行」，会在公开的演示服务器上用**真实计算服务**（Java 的 calc-engine・OCR・无职转生・房贷）和**剧本 LLM** 运行这个演示。
不使用真实 Claude，而且运行在 Cloud Run 的免费额度内，所以没有费用（用 1 USD 预算告警监控）。
服务器是 `python -m servers.web_api --public`（`servers/web_api/public.py`），镜像是 `deploy/cloudrun/Dockerfile`。

在本机试用：

```bash
docker build -f deploy/cloudrun/Dockerfile -t echolab-demo .
docker run --rm -p 8080:8080 echolab-demo              # → http://127.0.0.1:8080/api/health
```

公开的步骤（只做一次）：

1. 在 <https://console.cloud.google.com/> 开始使用 Google Cloud。需要登记信用卡，只用于身份验证，在免费额度内不会扣费。新账号还会送 90 天的试用额度。
2. 准备项目并关联结算账号。本仓库用的是默认项目「My First Project」（项目 ID `project-74011f80-dd2b-4a8c-b01`）。
3. 在**你自己的终端**里（Claude Code 的 `!` 不能在浏览器里登录，也不能输入）运行下面两条。第一条会显示一个网址：在浏览器里打开、登录 Google 账号、把显示的验证码贴回终端。如果提示找不到命令，先运行 `source ~/.bashrc`。
   ```bash
   gcloud auth login --no-launch-browser
   gcloud config set project project-74011f80-dd2b-4a8c-b01
   ```
4. 告诉 Claude 已登录。Claude 会运行 `deploy/cloudrun/setup.sh project-74011f80-dd2b-4a8c-b01`，完成：启用 API、建立 Artifact Registry（自动删除旧镜像）、服务账号、无密钥的 Workload Identity 联合、预算告警（结算账号是日元时为 150 JPY，不扣除试用额度来计算）、第一次部署、登记 GitHub 变量（`GCP_*`・`LIVE_API_URL`）。
5. 之后每次推送到 main，`.github/workflows/cloudrun.yml` 会自动部署；「web」工作流用 `LIVE_API_URL` 在网页上显示按钮。

试用期结束后：试用额度用完或到期（这个账号是 2027-01-03）时，如果不「升级」为付费账号，项目里的资源会被停止，演示服务器也会停。Cloud Run 的免费额度（Free Tier）在升级为付费账号后仍然有效，在额度内仍是 0 元；Google 不会自动升级，升级要自己在控制台操作。

没人使用时实例数会降到 0，下次调用时再启动（网页会显示"正在等待服务器启动"）。

## 结构

| 位置 | 内容 |
|---|---|
| `src/replay.ts` | 执行轨迹事件 → 回放的每一步（高亮的方框・箭头・出处）。不依赖 React 的纯函数（`replay.test.ts`） |
| `src/FlowDiagram.tsx`・`src/FloatingEdge.tsx` | 流程图。箭头是连接方框边框的直线 |
| `src/RunPlayer.tsx` | 一次运行的回放（逐步・自动播放・出处表・回答） |
| `src/ReplayView.tsx`・`src/EvalsView.tsx`・`src/LiveView.tsx` | 三个界面 |
| `../servers/web_api/` | 数据导出（`export.py`）与本机 API（`server.py`）。只用 Python 标准库 |
