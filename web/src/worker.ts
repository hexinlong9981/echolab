// EchoLab Web UI の Basic 認証 Worker。
// 密码存在 Cloudflare Worker secret WEB_PASSWORD 里，用户名不限制。
// 未设置密码时默认拒绝所有请求（fail closed）。

const REALM = 'Basic realm="EchoLab Web", charset="UTF-8"';

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

/** Authorization 头里的密码（Basic）。格式不对时返回 null。 */
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

function deny(status: number, text: string, challenge: boolean): Response {
  const headers: Record<string, string> = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
  };
  if (challenge) headers["WWW-Authenticate"] = REALM;
  return new Response(text, { status, headers });
}

interface Env {
  WEB_PASSWORD?: string;
  ASSETS: { fetch: (req: Request) => Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const expected = env.WEB_PASSWORD;
    if (!expected) return deny(503, "password not configured (set WEB_PASSWORD secret)", false);
    const given = passwordFrom(request.headers.get("Authorization"));
    if (given === null || !safeEqual(given, expected)) {
      return deny(401, "authentication required", true);
    }
    const res = await env.ASSETS.fetch(request);
    const out = new Response(res.body, res);
    out.headers.set("X-Robots-Tag", "noindex");
    out.headers.set("Cache-Control", "private, no-cache");
    return out;
  },
};
