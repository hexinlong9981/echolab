import { describe, expect, it } from "vitest";
import worker, { cookieToken, hashToken, passwordFrom, renderLoginPage, safeEqual } from "./worker";

describe("worker password-only authentication", () => {
  it("safeEqual compares strings correctly", () => {
    expect(safeEqual("secret123", "secret123")).toBe(true);
    expect(safeEqual("secret123", "secret124")).toBe(false);
    expect(safeEqual("secret123", "secret")).toBe(false);
    expect(safeEqual("", "")).toBe(true);
  });

  it("hashToken produces consistent sha256 hex string", async () => {
    const t1 = await hashToken("mypass");
    const t2 = await hashToken("mypass");
    const t3 = await hashToken("other");
    expect(t1).toHaveLength(64);
    expect(t1).toBe(t2);
    expect(t1).not.toBe(t3);
  });

  it("cookieToken extracts auth cookie properly", () => {
    expect(cookieToken("foo=1; echolab_auth=abc123token; bar=2")).toBe("abc123token");
    expect(cookieToken("echolab_auth=single-token")).toBe("single-token");
    expect(cookieToken("other=123")).toBeNull();
    expect(cookieToken(null)).toBeNull();
  });

  it("passwordFrom parses legacy basic auth header", () => {
    const header = "Basic dXNlcjpteS1wYXNz";
    expect(passwordFrom(header)).toBe("my-pass");
    expect(passwordFrom(null)).toBeNull();
    expect(passwordFrom("Bearer token")).toBeNull();
  });

  it("renderLoginPage contains only password field, no username field", () => {
    const html = renderLoginPage();
    expect(html).toContain('type="password"');
    expect(html).not.toContain('name="username"');
    expect(html).not.toContain('type="text"');
    expect(html).toContain('action="/__login"');
  });

  it("worker fetch returns 503 when password is not configured", async () => {
    const res = await worker.fetch(new Request("https://test.local/"), {
      ASSETS: { fetch: async () => new Response("ok") },
    });
    expect(res.status).toBe(503);
    expect(await res.text()).toContain("password not configured");
  });

  it("worker fetch returns 401 with login page when unauthenticated", async () => {
    const res = await worker.fetch(new Request("https://test.local/"), {
      WEB_PASSWORD: "correct-horse",
      ASSETS: { fetch: async () => new Response("ok") },
    });
    expect(res.status).toBe(401);
    const html = await res.text();
    expect(html).toContain('type="password"');
  });

  it("worker handles login submit correctly", async () => {
    const env = {
      WEB_PASSWORD: "mypassword",
      ASSETS: { fetch: async () => new Response("ok") },
    };

    // 错误的密码
    const badBody = new FormData();
    badBody.set("password", "wrong");
    const badRes = await worker.fetch(
      new Request("https://test.local/__login", { method: "POST", body: badBody }),
      env,
    );
    expect(badRes.status).toBe(401);
    expect(await badRes.text()).toContain("パスワードが正しくありません");

    // 正确的密码 -> 302 重定向并下发 Cookie
    const goodBody = new FormData();
    goodBody.set("password", "mypassword");
    const goodRes = await worker.fetch(
      new Request("https://test.local/__login", { method: "POST", body: goodBody }),
      env,
    );
    expect(goodRes.status).toBe(302);
    expect(goodRes.headers.get("Location")).toBe("/");
    const setCookie = goodRes.headers.get("Set-Cookie");
    expect(setCookie).toContain("echolab_auth=");
    expect(setCookie).toContain("HttpOnly");

    // 携带该 Cookie 可以成功访问页面
    const match = setCookie!.match(/echolab_auth=([^;]+)/);
    const token = match![1];
    const authedRes = await worker.fetch(
      new Request("https://test.local/data/index.json", {
        headers: { Cookie: `echolab_auth=${token}` },
      }),
      env,
    );
    expect(authedRes.status).toBe(200);
    expect(await authedRes.text()).toBe("ok");
  });
});
