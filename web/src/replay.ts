// 実行トレースの出来事を、回放の 1 コマずつに変える（React に依存しない純粋な関数。replay.test.ts で試験する）。
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
  | "compare"
  | "verifier"
  | "answer";

export type Tone = "active" | "ok" | "bad";

export interface Step {
  index: number;
  /** 見出し（日本語） */
  title: string;
  /** 補足（日本語） */
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
  core: "compare",
};

/** ツール（wire 名またはドメインのツール名）が届く箱。宣言されていないツールはゲートウェイで止まる。 */
export function serviceNode(tool: string, services: Record<string, string>): NodeId | null {
  // wire 名は「.」を「_」にしたもの（damage.expected → damage_expected）
  const service =
    services[tool] ?? Object.entries(services).find(([name]) => name.replaceAll(".", "_") === tool)?.[1];
  return service ? (SERVICE_NODES[service] ?? null) : null;
}

export function buildSteps(events: TraceRecord[], services: Record<string, string>): Step[] {
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
            title: "質問",
            detail: `${e.question}（ドメイン ${e.domain}、使えるツール ${e.tools.length} 個）`,
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
                title: "LLM がツールの呼び出しを求める",
                detail: `${calls.join("・")}（LLM は計算しない。数値はツールが出す）`,
                nodes: { agent: "active", llm: "active" },
                edges: ["agent>llm", "llm>agent"],
              }
            : {
                title: "LLM が回答のテンプレートを書く",
                detail: "数値はプレースホルダ [[出典ID]] で引用する。次に検証器が確かめる",
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
            title: `ツールの呼び出し：${e.name}`,
            detail: target
              ? "ゲートウェイが許可リストと入力の形を確かめ、サービスに渡す"
              : "ゲートウェイが許可リストを確かめる（このドメインで宣言されていない）",
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
              title: `拒否・誤り：${e.outcome.tool}`,
              detail: e.outcome.error,
              nodes: target ? { gateway: "bad", [target]: "bad", agent: "active" } : { gateway: "bad", agent: "active" },
              edges: ["gateway>agent"],
            },
            e,
          );
        } else {
          sources.push(...e.outcome.sources);
          push(
            {
              title: `結果：${e.outcome.tool}（呼び出し ${e.outcome.call_id}）`,
              detail: `出典 ID を ${e.outcome.sources.length} 個発行した（${e.outcome.sources
                .slice(0, 4)
                .map((s) => s.source_id)
                .join("・")}${e.outcome.sources.length > 4 ? " ほか" : ""}）`,
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
                title: `検証：下書き ${e.draft} は合格`,
                detail: `出典の無い数字は無い。引用 ${e.cited.length} 個をレンダラが数値に置き換える`,
                nodes: { verifier: "ok" },
                edges: ["agent>verifier"],
              }
            : {
                title: `検証：下書き ${e.draft} を差し戻し`,
                detail: e.problems.join(" / "),
                nodes: { verifier: "bad", agent: "active" },
                edges: ["agent>verifier", "verifier>agent"],
              },
          e,
        );
        break;
      case "answer":
        push(
          {
            title: e.status === "answered" ? "出典付きの回答" : `回答（${e.status}）`,
            detail:
              e.status === "answered"
                ? `引用した出典 ${e.cited.length} 個・差し戻し ${e.drafts_rejected} 回`
                : "数値を含まない定型の回答で終えた",
            nodes: { answer: e.status === "answered" ? "ok" : "bad", verifier: e.status === "answered" ? "ok" : "bad" },
            edges: ["verifier>answer"],
          },
          e,
        );
        break;
      case "budget_exceeded":
        push({ title: "コストの上限", detail: e.reason, nodes: { agent: "bad" }, edges: [] }, e);
        break;
      case "llm_error":
        push({ title: "LLM の呼び出しに失敗", detail: e.error, nodes: { llm: "bad", agent: "bad" }, edges: [] }, e);
        break;
    }
  }
  return steps;
}
