import { describe, expect, it } from "vitest";
import { borderPoint } from "./FloatingEdge";
import { buildSteps, serviceNode } from "./replay";
import type { TraceRecord } from "./types";

const services = {
  "damage.expected": "calc-engine",
  "echo.read_screenshot": "vision-mcp",
  "mortgage.equal_payment": "mortgage-calc",
  "compare.diff": "core",
};

const base = { ts: "2026-10-04T00:00:00Z", run_id: "r1" };
const ev = (e: Record<string, unknown>) => ({ ...base, ...e }) as TraceRecord;

describe("serviceNode", () => {
  it("wire 名とドメインのツール名のどちらでも、届く箱を返す", () => {
    expect(serviceNode("damage_expected", services)).toBe("calc-engine");
    expect(serviceNode("echo.read_screenshot", services)).toBe("vision-mcp");
    expect(serviceNode("mortgage_equal_payment", services)).toBe("mortgage-calc");
    expect(serviceNode("compare_diff", services)).toBe("compare");
  });

  it("宣言されていないツールは、どの箱にも届かない", () => {
    expect(serviceNode("shell_exec", services)).toBeNull();
  });
});

describe("buildSteps", () => {
  const events = [
    ev({ event: "question", question: "q", domain: "wuwa", llm: "ScriptedLLM", model: "m", tools: ["a", "b"] }),
    ev({ event: "llm_call", model: "m", stop_reason: "tool_use", text: "", usd: "0", tool_uses: [{ id: "t1", name: "damage_expected", input: {} }, { id: "t2", name: "shell_exec", input: {} }] }),
    ev({ event: "tool_call", tool_use_id: "t1", name: "damage_expected", input: {} }),
    ev({ event: "tool_call", tool_use_id: "t2", name: "shell_exec", input: {} }),
    ev({
      event: "tool_result",
      tool_use_id: "t1",
      outcome: { call_id: "c1", tool: "damage.expected", arguments: {}, error: null, sources: [{ source_id: "c1.total", value: "6192.000000", tool: "damage.expected", unverified_inputs: [] }] },
    }),
    ev({
      event: "tool_result",
      tool_use_id: "t2",
      outcome: { call_id: "c2", tool: "shell_exec", arguments: {}, error: "ツール shell_exec は使えません", sources: [] },
    }),
    ev({ event: "llm_call", model: "m", stop_reason: "end_turn", text: "x", usd: "0", tool_uses: [] }),
    ev({ event: "verdict", draft: 1, template: "936", ok: false, problems: ["数値「936」の出典がありません"], cited: [] }),
    ev({ event: "verdict", draft: 2, template: "[[c1.total]]", ok: true, problems: [], cited: ["c1.total"] }),
    ev({ event: "answer", status: "answered", answer: "6,192", cited: ["c1.total"], cost_usd: "0", drafts: 2, drafts_rejected: 1 }),
  ];
  const steps = buildSteps(events, services);

  it("出来事 1 つが 1 コマになる", () => {
    expect(steps).toHaveLength(events.length);
    expect(steps.map((s) => s.index)).toEqual(events.map((_, i) => i));
  });

  it("許可されたツールはサービスの箱まで届き、宣言されていないツールはゲートウェイで止まる", () => {
    expect(steps[2]?.edges).toEqual(["agent>gateway", "gateway>calc-engine"]);
    expect(steps[3]?.edges).toEqual(["agent>gateway"]);
    expect(steps[5]?.nodes.gateway).toBe("bad");
    expect(steps[5]?.detail).toContain("使えません");
  });

  it("出典は結果が返ったときから表に出る", () => {
    expect(steps[3]?.sources).toEqual([]);
    expect(steps[4]?.sources.map((s) => s.source_id)).toEqual(["c1.total"]);
    expect(steps.at(-1)?.sources).toHaveLength(1);
  });

  it("差し戻しは赤、合格と回答は緑になる", () => {
    expect(steps[7]?.nodes.verifier).toBe("bad");
    expect(steps[7]?.title).toContain("差し戻し");
    expect(steps[8]?.nodes.verifier).toBe("ok");
    expect(steps[9]?.nodes.answer).toBe("ok");
  });

  it("定型の回答（fallback）は赤になる", () => {
    const [step] = buildSteps(
      [ev({ event: "answer", status: "fallback", answer: "…", cited: [], cost_usd: "0", drafts: 3, drafts_rejected: 3 })],
      services,
    );
    expect(step?.nodes.answer).toBe("bad");
  });
});

describe("borderPoint", () => {
  it("中心から相手に向かう直線と、箱の枠の交点を返す", () => {
    const box = { x: 0, y: 0, w: 100, h: 40 };
    expect(borderPoint(box, 200, 0)).toEqual({ x: 50, y: 0 }); // 右へ → 右の辺
    expect(borderPoint(box, 0, -200)).toEqual({ x: 0, y: -20 }); // 上へ → 上の辺
    expect(borderPoint(box, 100, 100)).toEqual({ x: 20, y: 20 }); // 斜め → 先に当たる下の辺
  });
});
