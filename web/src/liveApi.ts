// 公開のデモサーバ（Google Cloud Run、ADR-0013）を呼ぶ。台本の LLM・実物の計算サービス。
// サーバの URL はビルドのときの環境変数 VITE_LIVE_API（例 https://echolab-demo-xxxxx.a.run.app）。
// 設定が無ければ、画面に「サーバで実行」のボタンを出さない。
import type { AskRequest } from "./data";
import type { RunRecord, TraceRecord } from "./types";

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

/** 質問またはデモをサーバで実行する。onEvent が渡されたときは SSE でリアルタイム受信する。 */
export async function askOnServer(
  base: string,
  req: AskRequest,
  fetchImpl: Fetch = fetch,
  onEvent?: (ev: TraceRecord) => void
): Promise<RunRecord> {
  const bodyData = onEvent ? { ...req, stream: true } : req;
  let res: Response;
  try {
    res = await fetchImpl(`${base}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(onEvent ? { Accept: "text/event-stream, application/json" } : {}),
      },
      body: JSON.stringify(bodyData),
    });
  } catch (e) {
    throw new LiveError("offline", (e as Error).message);
  }

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
              // skip malformed
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
  const doc = body as RunRecord;
  if (onEvent && Array.isArray(doc.events)) {
    for (const ev of doc.events) onEvent(ev);
  }
  return doc;
}

/** デモを 1 回、サーバで実行する。 */
export async function runOnServer(base: string, demo: string, fetchImpl: Fetch = fetch): Promise<RunRecord> {
  return askOnServer(base, { demo } as unknown as AskRequest, fetchImpl);
}
