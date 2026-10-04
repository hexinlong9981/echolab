import { describe, expect, it } from "vitest";
import worker, { cookieToken, hashToken, safeEqual } from "./worker";

describe("worker selective live-chat authentication", () => {
  it("safeEqual compares strings correctly", () => {
    expect(safeEqual("secret123", "secret123")).toBe(true);
    expect(safeEqual("secret123", "secret124")).toBe(false);
  });

  it("hashToken produces consistent sha256 hex string", async () => {
    const t1 = await hashToken("mypass");
    const t2 = await hashToken("mypass");
    expect(t1).toHaveLength(64);
    expect(t1).toBe(t2);
  });

  it("cookieToken extracts auth cookie properly", () => {
    expect(cookieToken("foo=1; echolab_auth=abc123token; bar=2")).toBe("abc123token");
    expect(cookieToken(null)).toBeNull();
  });

  it("public pages (Replay, Evals, static assets) are served without password", async () => {
    const res = await worker.fetch(new Request("https://test.local/"), {
      WEB_PASSWORD: "secret-password",
      ASSETS: { fetch: async () => new Response("index-html-content") },
    });
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("index-html-content");
  });

  it("/__auth endpoint reports status correctly", async () => {
    const env = {
      WEB_PASSWORD: "secret-password",
      ASSETS: { fetch: async () => new Response("ok") },
    };

    // 未携带 Cookie
    const res1 = await worker.fetch(new Request("https://test.local/__auth"), env);
    expect(res1.status).toBe(200);
    expect(await res1.json()).toEqual({ authenticated: false, configured: true });

    // 携带合法 Cookie
    const validToken = await hashToken("secret-password");
    const res2 = await worker.fetch(
      new Request("https://test.local/__auth", {
        headers: { Cookie: `echolab_auth=${validToken}` },
      }),
      env,
    );
    expect(await res2.json()).toEqual({ authenticated: true, configured: true });
  });

  it("/__login endpoint validates password and issues cookie", async () => {
    const env = {
      WEB_PASSWORD: "mypassword",
      ASSETS: { fetch: async () => new Response("ok") },
    };

    // 密码错误
    const badRes = await worker.fetch(
      new Request("https://test.local/__login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: "wrong" }),
      }),
      env,
    );
    expect(badRes.status).toBe(401);
    expect((await badRes.json() as { ok: boolean }).ok).toBe(false);

    // 密码正确
    const goodRes = await worker.fetch(
      new Request("https://test.local/__login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: "mypassword" }),
      }),
      env,
    );
    expect(goodRes.status).toBe(200);
    expect((await goodRes.json() as { ok: boolean }).ok).toBe(true);
    expect(goodRes.headers.get("Set-Cookie")).toContain("echolab_auth=");
  });
});
