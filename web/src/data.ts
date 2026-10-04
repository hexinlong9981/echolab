// 静的なデータ（data/*.json、CI が書き出す）と、手元の API（/api/*、ある場合だけ）を読む。
import type { DataIndex, LocalInfo, RunRecord, TraceRecord } from "./types";

/** 公開のデータに無いファイル（公開し直して変わった・消えたもの）。 */
export class DataMissingError extends Error {
  constructor(public readonly path: string) {
    super(`データが見つかりません: ${path}`);
  }
}

/** JSON を読む。404 や HTML（JSON でない応答）は DataMissingError にする。 */
async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const type = res.headers.get("content-type") ?? "";
  if (res.status === 404 || (res.ok && !type.includes("json"))) throw new DataMissingError(path);
  if (!res.ok) throw new Error(`${path}（${res.status}）`);
  return (await res.json()) as T;
}

export function loadIndex(): Promise<DataIndex> {
  // 公開し直したら新しい一覧を読むよう、毎回サーバに確かめる
  return fetchJson<DataIndex>("data/index.json", { cache: "no-cache" });
}

const runs = new Map<string, Promise<RunRecord>>();

/** 記録を読む（runs/<キー>.json）。失敗したものは覚えておかず、次に読み直す。 */
export function loadRun(key: string): Promise<RunRecord> {
  let p = runs.get(key);
  if (!p) {
    p = fetchJson<RunRecord>(`data/runs/${encodeURIComponent(key)}.json`);
    runs.set(key, p);
    p.catch(() => runs.delete(key));
  }
  return p;
}

/** 読んだ記録を忘れる（一覧を読み直したとき）。 */
export function forgetRuns(): void {
  runs.clear();
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
  llm?: "scripted" | "anthropic" | "gemini";
  demo?: string;
  question?: string;
  domain?: string;
  /** 利用者が指定する進み具合（無職転生のパック。例 novel:5） */
  progress?: string;
  fake_backend?: boolean;
  stream?: boolean;
}

export async function ask(
  req: AskRequest,
  base?: string | null,
  onEvent?: (ev: TraceRecord) => void
): Promise<RunRecord> {
  const url = base ? `${base.replace(/\/+$/, "")}/api/ask` : "api/ask";
  const bodyData = onEvent ? { ...req, stream: true } : req;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(onEvent ? { Accept: "text/event-stream, application/json" } : {}),
    },
    body: JSON.stringify(bodyData),
  });

  const contentType = res.headers.get("content-type") ?? "";
  if (res.ok && contentType.includes("text/event-stream") && res.body) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const events: TraceRecord[] = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        for (const line of block.split("\n")) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const payload = trimmed.slice(6);
            if (payload === "[DONE]") continue;
            try {
              const ev = JSON.parse(payload) as TraceRecord;
              events.push(ev);
              onEvent?.(ev);
            } catch {
              // skip malformed chunk
            }
          }
        }
      }
    }

    const answerEv = events.find((e) => e.event === "answer");
    return {
      run_id: events[0]?.run_id ?? "live",
      domain: req.domain ?? "wuwa",
      llm: req.llm ?? "gemini",
      fake_backend: Boolean(req.fake_backend),
      status: answerEv ? (answerEv as { status?: string }).status ?? null : null,
      context: req.progress ? { progress: req.progress } : {},
      events,
    };
  }

  const doc = (await res.json()) as RunRecord | { error: string };
  if (!res.ok || "error" in doc) throw new Error("error" in doc ? doc.error : `失敗しました（${res.status}）`);
  if (onEvent && "events" in doc && Array.isArray(doc.events)) {
    for (const ev of doc.events) onEvent(ev);
  }
  return doc;
}
