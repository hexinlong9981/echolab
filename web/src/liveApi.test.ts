import { describe, expect, it } from "vitest";
import { classifyError, LiveError, liveApiBase, runOnServer, wake } from "./liveApi";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("liveApiBase", () => {
  it("URL の末尾の / を除き、設定が無ければ null", () => {
    expect(liveApiBase("https://echolab-demo-abc123-uc.a.run.app/")).toBe("https://echolab-demo-abc123-uc.a.run.app");
    expect(liveApiBase("")).toBeNull();
    expect(liveApiBase(undefined)).toBeNull();
    expect(liveApiBase("javascript:alert(1)")).toBeNull();
  });
});

describe("classifyError", () => {
  it("状態と本文の code から、画面の文言の種類を決める", () => {
    expect(classifyError(429, { code: "rate_limited" })).toBe("rate_limited");
    expect(classifyError(503, { code: "busy" })).toBe("busy");
    expect(classifyError(504, { code: "timeout" })).toBe("timeout");
    expect(classifyError(503, null)).toBe("offline");
    expect(classifyError(403, { code: "llm_not_allowed" })).toBe("other");
  });
});

describe("runOnServer", () => {
  it("デモの ID だけを送り、記録を返す", async () => {
    let sent: RequestInit | undefined;
    const run = await runOnServer("https://x", "demo-mortgage", async (_url, init) => {
      sent = init;
      return json(200, { run_id: "r", status: "answered", events: [] });
    });
    expect(run.status).toBe("answered");
    expect(JSON.parse(String(sent?.body))).toEqual({ demo: "demo-mortgage" });
  });

  it("回数の上限・接続できないときは種類つきの誤りにする", async () => {
    await expect(runOnServer("https://x", "d", async () => json(429, { error: "e", code: "rate_limited" }))).rejects.toMatchObject({
      code: "rate_limited",
    });
    const failed = runOnServer("https://x", "d", async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(failed).rejects.toBeInstanceOf(LiveError);
    await expect(failed).rejects.toMatchObject({ code: "offline" });
  });
});

describe("wake", () => {
  it("health が応答したら起きたとみなす", async () => {
    expect(await wake("https://x", async () => json(200, { ok: true }), 1000)).toBe(true);
  });
});
