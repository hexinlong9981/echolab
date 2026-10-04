// 書き出し（servers/web_api/export.py）と手元の API（servers/web_api/server.py）が返す JSON の形。

export interface SourceValue {
  source_id: string;
  value: string;
  tool: string;
  unverified_inputs: string[];
}

export interface ToolUse {
  id: string;
  name: string;
  input: unknown;
}

export type TraceEvent =
  | { event: "question"; question: string; domain: string; llm: string; model: string; tools: string[] }
  | { event: "llm_call"; model: string; stop_reason: string; text: string; tool_uses: ToolUse[]; usd: string }
  | { event: "tool_call"; tool_use_id: string; name: string; input: unknown }
  | {
      event: "tool_result";
      tool_use_id: string;
      outcome: { call_id: string; tool: string; arguments: unknown; sources: SourceValue[]; error: string | null };
    }
  | { event: "verdict"; draft: number; template: string; ok: boolean; problems: string[]; cited: string[] }
  | {
      event: "answer";
      status: string;
      answer: string;
      cited: string[];
      cost_usd: string;
      drafts: number;
      drafts_rejected: number;
    }
  | { event: "budget_exceeded"; reason: string }
  | { event: "llm_error"; kind: string; error: string };

export type TraceRecord = TraceEvent & { ts: string; run_id: string };

export interface RunRecord {
  run_id: string;
  domain: string | null;
  llm: string | null;
  fake_backend: boolean;
  status: string | null;
  events: TraceRecord[];
}

export interface Demo {
  id: string;
  title: string;
  domain: string;
  script: string;
  question: string;
  run_id: string;
  status: string;
}

export interface CaseSummary {
  id: string;
  title: string;
  status: string;
  passed: boolean;
  faithful: boolean;
  drafts: number;
  drafts_rejected: number;
  tool_errors: number;
  cited: string[];
  failures: string[];
  run_id: string | null;
}

export interface Suite {
  id: string;
  title: string;
  cases_path?: string;
  domain: string;
  faithfulness: number;
  draft_rejection_rate: number;
  passed: number;
  total: number;
  tool_errors: number;
  ok: boolean;
  cases: CaseSummary[];
}

export interface DataIndex {
  generated_at: string;
  commit: string | null;
  demos: Demo[];
  suites: Suite[];
  services: Record<string, string>;
}

export interface LocalInfo {
  domains: string[];
  demos: Omit<Demo, "run_id" | "status">[];
  has_api_key: boolean;
  ocr: boolean;
  caps_usd: { daily: string; monthly: string };
}
