// 静的なデータ（data/*.json、CI が書き出す）と、手元の API（/api/*、ある場合だけ）を読む。
import type { DataIndex, LocalInfo, RunRecord } from "./types";

export async function loadIndex(): Promise<DataIndex> {
  const res = await fetch("data/index.json");
  if (!res.ok) throw new Error(`data/index.json を読めません（${res.status}）`);
  return (await res.json()) as DataIndex;
}

const runs = new Map<string, Promise<RunRecord>>();

export function loadRun(runId: string): Promise<RunRecord> {
  let p = runs.get(runId);
  if (!p) {
    p = fetch(`data/runs/${encodeURIComponent(runId)}.json`).then(async (res) => {
      if (!res.ok) throw new Error(`実行 ${runId} を読めません（${res.status}）`);
      return (await res.json()) as RunRecord;
    });
    runs.set(runId, p);
  }
  return p;
}

/** 手元の API があれば情報を返す。公開のサイト（静的）では null。 */
export async function loadLocalInfo(): Promise<LocalInfo | null> {
  try {
    const res = await fetch("api/info", { cache: "no-store" });
    if (!res.ok || !res.headers.get("content-type")?.includes("application/json")) return null;
    return (await res.json()) as LocalInfo;
  } catch {
    return null;
  }
}

export interface AskRequest {
  llm: "scripted" | "anthropic";
  demo?: string;
  question?: string;
  domain?: string;
  fake_backend: boolean;
}

export async function ask(req: AskRequest): Promise<RunRecord> {
  const res = await fetch("api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const doc = (await res.json()) as RunRecord | { error: string };
  if (!res.ok || "error" in doc) throw new Error("error" in doc ? doc.error : `失敗しました（${res.status}）`);
  return doc;
}
