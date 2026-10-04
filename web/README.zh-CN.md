# web/ — 回放・评估看板・本机运行界面

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

用 React + TypeScript + Vite 做的网页界面（M5、[ADR-0011](../docs/adr/zh-CN/0011-网页界面与公开方针.md)）。**零费用**是最优先的原则。

| 界面 | 公开网站 | 本机 | 内容 |
|---|---|---|---|
| 回放 | ✅ | ✅ | 逐步播放执行轨迹。用流程图（React Flow）以颜色标出经过的方框、退回和拒绝，并显示当时的出处表。用网址 `#replay/<执行 ID>/<步>` 可以直接打开某个时刻 |
| 评估 | ✅ | ✅ | 数值忠实度（鸣潮・房贷）与注入评估的指标和每个用例的结果，可从每个用例跳到回放 |
| 运行（本机） | — | ✅ | 用剧本演示或真实 Claude（有 API 密钥时，受成本上限保护）提问，并当场回放 |

公开网站只有静态文件（不运行服务器和 LLM，所以没有费用，也不会被别人用掉你的 API）。
回放数据是 CI 用剧本模式（无需 API 密钥、测试用计算服务）导出的，不是真实 LLM 的回答。

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

## 发布到 Cloudflare Pages（只需手动做一次）

CI（`.github/workflows/web.yml`）每次推送到 main 都会构建，有下面两个 Secrets 时就发布；没有时只跳过发布这一步。

1. 在 <https://dash.cloudflare.com/sign-up> 注册 Cloudflare 账号（免费，不需要信用卡）。
2. 记下**账号 ID**：在后台「Workers & Pages」页面右侧，或在「Account home」中账号的「…」→「Copy account ID」。
3. 创建 **API 令牌**：右上角头像 →「My Profile」→「API Tokens」→「Create Token」→「Create Custom Token」。
   - Permissions：`Account`・`Cloudflare Pages`・`Edit`（只要这一项）
   - Account Resources：`Include`・你的账号
   - 记下创建后显示的令牌（只显示一次）。
4. 在 GitHub 仓库登记 Secrets：「Settings」→「Secrets and variables」→「Actions」→「New repository secret」，
   登记 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID`。用命令的话：
   ```bash
   gh secret set CLOUDFLARE_API_TOKEN -R hexinlong9981/echolab     # 粘贴后回车
   gh secret set CLOUDFLARE_ACCOUNT_ID -R hexinlong9981/echolab
   ```
5. 在「Actions」→「web」→「Run workflow」运行（或等下一次推送）。第一次会先创建项目 `echolab` 再发布。
   网址是 `https://echolab.pages.dev/`（名字被占用时 Cloudflare 会另取一个，可在后台确认）。

在 Cloudflare Pages 免费方案的范围内运行（流量不限，每月最多 500 次构建；构建在 GitHub Actions 中完成，不使用 Cloudflare 的构建）。
令牌只有编辑 Pages 的权限，即使泄露也改不了其他设置。不再需要时请在 Cloudflare 后台作废。

## 结构

| 位置 | 内容 |
|---|---|
| `src/replay.ts` | 执行轨迹事件 → 回放的每一步（高亮的方框・箭头・出处）。不依赖 React 的纯函数（`replay.test.ts`） |
| `src/FlowDiagram.tsx`・`src/FloatingEdge.tsx` | 流程图。箭头是连接方框边框的直线 |
| `src/RunPlayer.tsx` | 一次运行的回放（逐步・自动播放・出处表・回答） |
| `src/ReplayView.tsx`・`src/EvalsView.tsx`・`src/LiveView.tsx` | 三个界面 |
| `../servers/web_api/` | 数据导出（`export.py`）与本机 API（`server.py`）。只用 Python 标准库 |
