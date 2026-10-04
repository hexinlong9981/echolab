// 公開のデモサーバ（Google Cloud Run、ADR-0013）を呼ぶ。台本の LLM・実物の計算サービス。
// サーバの URL はビルドのときの環境変数 VITE_LIVE_API（例 https://echolab-demo-xxxxx.a.run.app）。
// 設定が無ければ、画面に「サーバで実行」のボタンを出さない。
import type { RunRecord } from "./types";

export type LiveErrorCode = "rate_limited" | "busy" | "timeout" | "offline" | "other";

export class LiveError extends Error {
  constructor(
    public readonly code: LiveErrorCode,
    message: string,
  ) {
    super(message);
  }
}

/** サーバの URL（末尾の / を除く）。無ければ null。 */
export function liveApiBase(raw: string | undefined = import.meta.env.VITE_LIVE_API as string | undefined): string | null {
  const base = (raw ?? "").trim().replace(/\/+$/, "");
  return /^https?:\/\//.test(base) ? base : null;
}

/** サーバの応答（HTTP の状態と本文）から、画面で出し分ける誤りの種類を決める。 */
export function classifyError(status: number, body: unknown): LiveErrorCode {
  const code = typeof body === "object" && body !== null ? (body as { code?: unknown }).code : undefined;
  if (status === 429 || code === "rate_limited") return "rate_limited";
  if (code === "busy") return "busy";
  if (status === 504 || code === "timeout") return "timeout";
  if (status === 502 || status === 503) return "offline";
  return "other";
}

type Fetch = typeof fetch;

/** 休止中のサーバを起こす（起動を待つ）。起きたら true。 */
export async function wake(base: string, fetchImpl: Fetch = fetch, timeoutMs = 120_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetchImpl(`${base}/api/health`, { cache: "no-store" });
      if (res.ok) return true;
    } catch {
      // 起動中は接続できないことがある
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  return false;
}

/** デモを 1 回、サーバで実行する。 */
export async function runOnServer(base: string, demo: string, fetchImpl: Fetch = fetch): Promise<RunRecord> {
  let res: Response;
  try {
    res = await fetchImpl(`${base}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ demo }),
    });
  } catch (e) {
    throw new LiveError("offline", (e as Error).message);
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // HTML のエラーページ（起動中など）
  }
  if (!res.ok || body === null || (typeof body === "object" && "error" in (body as object))) {
    const message = typeof body === "object" && body !== null ? String((body as { error?: unknown }).error ?? "") : "";
    throw new LiveError(classifyError(res.status, body), message || `HTTP ${res.status}`);
  }
  return body as RunRecord;
}
