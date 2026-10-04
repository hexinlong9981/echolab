import { afterEach, describe, expect, it, vi } from "vitest";
import { DataMissingError, forgetRuns, loadIndex, loadRun } from "./data";

function respond(status: number, body: string, type: string) {
  return vi.fn(async () => new Response(body, { status, headers: { "content-type": type } }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetRuns();
});

describe("loadRun", () => {
  it("読めた記録を返す", async () => {
    vi.stubGlobal("fetch", respond(200, '{"run_id":"r1","events":[]}', "application/json"));
    await expect(loadRun("demo-compare-builds")).resolves.toMatchObject({ run_id: "r1" });
  });

  it("404 は DataMissingError（公開し直されて無くなった記録）", async () => {
    vi.stubGlobal("fetch", respond(404, "not found", "text/plain"));
    await expect(loadRun("old")).rejects.toBeInstanceOf(DataMissingError);
  });

  it("JSON でない応答（index.html など）も DataMissingError にし、JSON として読まない", async () => {
    vi.stubGlobal("fetch", respond(200, "<!doctype html><html></html>", "text/html"));
    await expect(loadRun("old")).rejects.toBeInstanceOf(DataMissingError);
  });

  it("失敗した記録は覚えず、次は読み直す", async () => {
    vi.stubGlobal("fetch", respond(404, "", "text/plain"));
    await expect(loadRun("k")).rejects.toBeInstanceOf(DataMissingError);
    const ok = respond(200, '{"run_id":"r2","events":[]}', "application/json");
    vi.stubGlobal("fetch", ok);
    await expect(loadRun("k")).resolves.toMatchObject({ run_id: "r2" });
    expect(ok).toHaveBeenCalledTimes(1);
  });
});

describe("loadIndex", () => {
  it("一覧は毎回サーバに確かめる（cache: no-cache）", async () => {
    const f = respond(200, '{"demos":[],"suites":[]}', "application/json");
    vi.stubGlobal("fetch", f);
    await loadIndex();
    expect(f).toHaveBeenCalledWith("data/index.json", { cache: "no-cache" });
  });
});
