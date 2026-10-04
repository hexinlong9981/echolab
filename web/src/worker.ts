// EchoLab Web UI の認証 Worker。
// 密码仅存在 Cloudflare Worker secret WEB_PASSWORD 里，无需用户名。
// 未登录时展示简洁的单密码输入页，验证通过后发放安全 HttpOnly Cookie。

/** 长度和内容都按固定时间比较，避免通过响应时间推测密码。 */
export function safeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const x = enc.encode(a);
  const y = enc.encode(b);
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

/** 基于 Web Crypto 生成单向会话 Token。 */
export async function hashToken(password: string): Promise<string> {
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest("SHA-256", enc.encode(password + ":echolab-session-v1"));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** 从 Cookie 请求头中解析 Token。 */
export function cookieToken(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(/(?:^|;\s*)echolab_auth=([^;]+)/);
  return match && match[1] ? decodeURIComponent(match[1]) : null;
}

/** Authorization 头里的密码（Basic，兼顾脚本调用）。格式不对时返回 null。 */
export function passwordFrom(header: string | null): string | null {
  if (!header || !header.startsWith("Basic ")) return null;
  let decoded: string;
  try {
    const bytes = Uint8Array.from(atob(header.slice(6).trim()), (c) => c.charCodeAt(0));
    decoded = new TextDecoder().decode(bytes);
  } catch {
    return null;
  }
  const i = decoded.indexOf(":");
  return i < 0 ? null : decoded.slice(i + 1);
}

export function renderLoginPage(errorMsg?: string): string {
  const errHtml = errorMsg ? `<div class="err">${errorMsg}</div>` : "";
  return `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EchoLab · 認証</title>
  <style>
    :root {
      --bg: #0d1117;
      --card: #161b22;
      --line: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #2f81f7;
      --accent-hover: #388bfd;
      --err: #f85149;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 32px 28px;
      width: 100%;
      max-width: 320px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    h1 {
      font-size: 1.25rem;
      margin: 0 0 6px;
      font-weight: 600;
      text-align: center;
      letter-spacing: -0.02em;
    }
    .sub {
      font-size: 0.82rem;
      color: var(--muted);
      margin: 0 0 20px;
      text-align: center;
      line-height: 1.4;
    }
    input[type="password"] {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      background: var(--bg);
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      font-size: 0.95rem;
      margin-bottom: 14px;
      transition: border-color 0.2s;
    }
    input[type="password"]:focus {
      outline: none;
      border-color: var(--accent);
    }
    button {
      width: 100%;
      padding: 10px;
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover {
      background: var(--accent-hover);
    }
    .err {
      color: var(--err);
      background: rgba(248, 81, 73, 0.1);
      border: 1px solid rgba(248, 81, 73, 0.4);
      border-radius: 6px;
      font-size: 0.82rem;
      padding: 8px 10px;
      margin-bottom: 14px;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>EchoLab</h1>
    <p class="sub">パスワードを入力してください<br><span style="font-size:0.78rem">请输入访问密码</span></p>
    ${errHtml}
    <form method="POST" action="/__login">
      <input type="password" name="password" autofocus placeholder="Password" required autocomplete="current-password">
      <button type="submit">アクセス / 进入</button>
    </form>
  </div>
</body>
</html>`;
}

interface Env {
  WEB_PASSWORD?: string;
  ASSETS: { fetch: (req: Request) => Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const expected = env.WEB_PASSWORD;
    if (!expected) {
      return new Response("password not configured (set WEB_PASSWORD secret)", {
        status: 503,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Robots-Tag": "noindex",
        },
      });
    }

    const url = new URL(request.url);
    const expectedToken = await hashToken(expected);

    // 1. 已有 Cookie 认证
    const cookie = cookieToken(request.headers.get("Cookie"));
    if (cookie && safeEqual(cookie, expectedToken)) {
      const res = await env.ASSETS.fetch(request);
      const out = new Response(res.body, res);
      out.headers.set("X-Robots-Tag", "noindex");
      out.headers.set("Cache-Control", "private, no-cache");
      return out;
    }

    // 2. 既有 Basic Auth 请求头兼容（便于 curl 等工具直接调用）
    const basicPass = passwordFrom(request.headers.get("Authorization"));
    if (basicPass && safeEqual(basicPass, expected)) {
      const res = await env.ASSETS.fetch(request);
      const out = new Response(res.body, res);
      out.headers.set("X-Robots-Tag", "noindex");
      out.headers.set("Cache-Control", "private, no-cache");
      return out;
    }

    // 3. 处理密码表单提交
    if (url.pathname === "/__login" && request.method === "POST") {
      let submittedPassword = "";
      try {
        const formData = await request.formData();
        submittedPassword = String(formData.get("password") ?? "");
      } catch {
        // 请求体异常
      }

      if (submittedPassword && safeEqual(submittedPassword, expected)) {
        return new Response(null, {
          status: 302,
          headers: {
            Location: "/",
            "Set-Cookie": `echolab_auth=${expectedToken}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`,
            "Cache-Control": "no-store",
          },
        });
      }

      return new Response(renderLoginPage("パスワードが正しくありません / 密码不正确"), {
        status: 401,
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Robots-Tag": "noindex",
        },
      });
    }

    // 4. 退出登录接口
    if (url.pathname === "/__logout") {
      return new Response(null, {
        status: 302,
        headers: {
          Location: "/",
          "Set-Cookie": "echolab_auth=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0",
          "Cache-Control": "no-store",
        },
      });
    }

    // 5. 其余所有未认证请求展示单密码登录页面
    return new Response(renderLoginPage(), {
      status: 401,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex",
      },
    });
  },
};
