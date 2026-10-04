// 静的なデータ（data/*.json、CI が書き出す）と、手元の API（/api/*、ある場合だけ）を読む。
import type { DataIndex, LocalInfo, RunRecord } from "./types";

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
  llm: "scripted" | "anthropic";
  demo?: string;
  question?: string;
  domain?: string;
  /** 利用者が指定する進み具合（無職転生のパック。例 novel:5） */
  progress?: string;
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
