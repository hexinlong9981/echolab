// 実行トレースの出来事を、回放の 1 コマずつに変える（React に依存しない純粋な関数。replay.test.ts で試験する）。
import { type T, translate } from "./i18n";
import type { SourceValue, TraceRecord } from "./types";

/** 図の箱。 */
export type NodeId =
  | "user"
  | "agent"
  | "llm"
  | "gateway"
  | "calc-engine"
  | "mortgage-calc"
  | "vision-mcp"
  | "mushoku-lore"
  | "compare"
  | "verifier"
  | "answer";

export type Tone = "active" | "ok" | "bad";

export interface Step {
  index: number;
  /** 見出し（m が返す形。画面では HTML、試験ではプレーンテキスト） */
  title: string;
  /** 補足 */
  detail: string;
  /** 光らせる箱と色 */
  nodes: Partial<Record<NodeId, Tone>>;
  /** 光らせる矢印（`from>to`） */
  edges: string[];
  /** この時点までに発行された出典（右の表に出す） */
  sources: SourceValue[];
  event: TraceRecord;
}

const SERVICE_NODES: Record<string, NodeId> = {
  "calc-engine": "calc-engine",
  "mortgage-calc": "mortgage-calc",
  "vision-mcp": "vision-mcp",
  "mushoku-lore": "mushoku-lore",
  core: "compare",
};

/** ツール（wire 名またはドメインのツール名）が届く箱。宣言されていないツールはゲートウェイで止まる。 */
export function serviceNode(tool: string, services: Record<string, string>): NodeId | null {
  // wire 名は「.」を「_」にしたもの（damage.expected → damage_expected）
  const service =
    services[tool] ?? Object.entries(services).find(([name]) => name.replaceAll(".", "_") === tool)?.[1];
  return service ? (SERVICE_NODES[service] ?? null) : null;
}

/** 既定の文言：日本語のプレーンテキスト。 */
const plainJa: T = (key, params) => translate("ja", key, params);

export function buildSteps(events: TraceRecord[], services: Record<string, string>, m: T = plainJa): Step[] {
  const steps: Step[] = [];
  const sources: SourceValue[] = [];
  const callTarget = new Map<string, NodeId | null>();
  const push = (s: Omit<Step, "index" | "sources" | "event">, event: TraceRecord) =>
    steps.push({ ...s, index: steps.length, sources: [...sources], event });

  for (const e of events) {
    switch (e.event) {
      case "question":
        push(
          {
            title: m("s.question"),
            detail: m("s.question.d", { question: e.question, domain: e.domain, n: e.tools.length }),
            nodes: { user: "active", agent: "active" },
            edges: ["user>agent"],
          },
          e,
        );
        break;
      case "llm_call": {
        const calls = e.tool_uses.map((u) => u.name);
        push(
          calls.length > 0
            ? {
                title: m("s.toolUse"),
                detail: m("s.toolUse.d", { tools: calls.join("・") }),
                nodes: { agent: "active", llm: "active" },
                edges: ["agent>llm", "llm>agent"],
              }
            : {
                title: m("s.template"),
                detail: m("s.template.d"),
                nodes: { agent: "active", llm: "active" },
                edges: ["agent>llm", "llm>agent"],
              },
          e,
        );
        break;
      }
      case "tool_call": {
        const target = serviceNode(e.name, services);
        callTarget.set(e.tool_use_id, target);
        push(
          {
            title: m("s.call", { tool: e.name }),
            detail: target ? m("s.call.ok") : m("s.call.denied"),
            nodes: target ? { agent: "active", gateway: "active", [target]: "active" } : { agent: "active", gateway: "active" },
            edges: target ? ["agent>gateway", `gateway>${target}`] : ["agent>gateway"],
          },
          e,
        );
        break;
      }
      case "tool_result": {
        const target = callTarget.get(e.tool_use_id) ?? null;
        if (e.outcome.error) {
          push(
            {
              title: m("s.error", { tool: e.outcome.tool }),
              detail: m("raw", { text: e.outcome.error }),
              nodes: target ? { gateway: "bad", [target]: "bad", agent: "active" } : { gateway: "bad", agent: "active" },
              edges: ["gateway>agent"],
            },
            e,
          );
        } else {
          sources.push(...e.outcome.sources);
          push(
            {
              title: m("s.result", { tool: e.outcome.tool, call: e.outcome.call_id }),
              detail: m("s.result.d", {
                n: e.outcome.sources.length,
                ids:
                  e.outcome.sources
                    .slice(0, 4)
                    .map((s) => s.source_id)
                    .join("・") + (e.outcome.sources.length > 4 ? m("s.more") : ""),
              }),
              nodes: target ? { [target]: "ok", gateway: "ok", agent: "active" } : { gateway: "ok", agent: "active" },
              edges: target ? [`${target}>gateway`, "gateway>agent"] : ["gateway>agent"],
            },
            e,
          );
        }
        break;
      }
      case "verdict":
        push(
          e.ok
            ? {
                title: m("s.pass", { draft: e.draft }),
                detail: m("s.pass.d", { n: e.cited.length }),
                nodes: { verifier: "ok" },
                edges: ["agent>verifier"],
              }
            : {
                title: m("s.reject", { draft: e.draft }),
                detail: m("raw", { text: e.problems.join(" / ") }),
                nodes: { verifier: "bad", agent: "active" },
                edges: ["agent>verifier", "verifier>agent"],
              },
          e,
        );
        break;
      case "answer":
        push(
          {
            title: e.status === "answered" ? m("s.answer") : m("s.answerOther", { status: e.status }),
            detail:
              e.status === "answered"
                ? m("s.answer.d", { n: e.cited.length, rejected: e.drafts_rejected })
                : m("s.fallback.d"),
            nodes: { answer: e.status === "answered" ? "ok" : "bad", verifier: e.status === "answered" ? "ok" : "bad" },
            edges: ["verifier>answer"],
          },
          e,
        );
        break;
      case "budget_exceeded":
        push({ title: m("s.budget"), detail: m("raw", { text: e.reason }), nodes: { agent: "bad" }, edges: [] }, e);
        break;
      case "llm_error":
        push({ title: m("s.llmError"), detail: m("raw", { text: e.error }), nodes: { llm: "bad", agent: "bad" }, edges: [] }, e);
        break;
    }
  }
  return steps;
}
