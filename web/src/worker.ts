// EchoLab Web UI の認証 Worker。
// 《回放》（Replay）与《评估》（Evals）以及所有静态文件完全公开，免密访问。
// 仅在《即时对话》时通过 /__auth 与 /__login 进行按需鉴权与 Cookie 发放。

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

interface Env {
  WEB_PASSWORD?: string;
  ASSETS: { fetch: (req: Request) => Promise<Response> };
}

function jsonResponse(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex",
      ...headers,
    },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const expected = env.WEB_PASSWORD;
    const url = new URL(request.url);

    // 1. 查询当前鉴权状态接口（供即时对话页面查询）
    if (url.pathname === "/__auth") {
      if (!expected) {
        return jsonResponse({ authenticated: false, configured: false });
      }
      const expectedToken = await hashToken(expected);
      const cookie = cookieToken(request.headers.get("Cookie"));
      const isAuthed = Boolean(cookie && safeEqual(cookie, expectedToken));
      return jsonResponse({ authenticated: isAuthed, configured: true });
    }

    // 2. 登录接口（即时对话解锁）
    if (url.pathname === "/__login" && request.method === "POST") {
      if (!expected) {
        return jsonResponse({ ok: false, error: "password_not_configured" }, 503);
      }
      let submittedPassword = "";
      try {
        const contentType = request.headers.get("content-type") ?? "";
        if (contentType.includes("application/json")) {
          const body = (await request.json()) as { password?: string };
          submittedPassword = String(body.password ?? "");
        } else {
          const formData = await request.formData();
          submittedPassword = String(formData.get("password") ?? "");
        }
      } catch {
        // 请求体异常
      }

      if (submittedPassword && safeEqual(submittedPassword, expected)) {
        const expectedToken = await hashToken(expected);
        return jsonResponse(
          { ok: true },
          200,
          {
            "Set-Cookie": `echolab_auth=${expectedToken}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`,
          }
        );
      }

      return jsonResponse({ ok: false, error: "invalid_password" }, 401);
    }

    // 3. 退出登录接口
    if (url.pathname === "/__logout") {
      return jsonResponse(
        { ok: true },
        200,
        {
          "Set-Cookie": "echolab_auth=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0",
        }
      );
    }

    // 4. 所有其他请求（主页、回放、评估、静态资源）一律公开直接访问
    const res = await env.ASSETS.fetch(request);
    const out = new Response(res.body, res);
    out.headers.set("X-Robots-Tag", "noindex");
    return out;
  },
};
