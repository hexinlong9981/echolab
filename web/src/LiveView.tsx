import { useState } from "react";
import { type AskRequest, ask } from "./data";
import { titleText, useI18n } from "./i18n";
import { LiveError, askOnServer, wake } from "./liveApi";
import { Question } from "./Question";
import { RunPlayer } from "./RunPlayer";
import { Tx } from "./Tx";
import type { LocalInfo, RunRecord } from "./types";

/** リアルタイム対話・実行画面（手元の API または公開の Cloud Run デモサーバ）。 */
export function LiveView({
  info,
  services,
  apiBase,
}: {
  info: LocalInfo;
  services: Record<string, string>;
  apiBase?: string | null;
}) {
  const { lang, t } = useI18n();
  const [mode, setMode] = useState<"scripted" | "gemini" | "anthropic">(apiBase ? "gemini" : "scripted");
  const [demo, setDemo] = useState(info.demos[0]?.id ?? "");
  const [question, setQuestion] = useState("");
  const [domain, setDomain] = useState(info.domains.includes("wuwa") ? "wuwa" : (info.domains[0] ?? ""));
  const [progress, setProgress] = useState("novel:1");
  const [fake, setFake] = useState(!apiBase);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);

  const submit = async () => {
    const isScripted = mode === "scripted";
    const req: AskRequest = isScripted
      ? { llm: "scripted", demo, fake_backend: apiBase ? false : fake }
      : {
          llm: mode,
          question,
          domain,
          fake_backend: apiBase ? false : fake,
          ...(domain === "mushoku" ? { progress } : {}),
        };
    setBusy(true);
    setError(null);
    setStatusText(null);
    try {
      if (apiBase) {
        setStatusText(t("server.waking") || "Connecting...");
        const awake = await wake(apiBase);
        if (!awake) throw new LiveError("offline", "Server wake timeout");
        setStatusText(t("live.running"));
        setRun(await askOnServer(apiBase, req));
      } else {
        setRun(await ask(req));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setStatusText(null);
    }
  };

  const selected = info.demos.find((d) => d.id === demo);

  return (
    <main className="live pad">
      <p className="muted">
        <Tx k="live.intro" p={{ daily: info.caps_usd.daily, monthly: info.caps_usd.monthly }} />
      </p>
      <div className="form">
        <label>
          <input type="radio" checked={mode === "gemini"} onChange={() => setMode("gemini")} /> <Tx k="live.gemini" />
        </label>
        <label>
          <input type="radio" checked={mode === "scripted"} onChange={() => setMode("scripted")} /> <Tx k="live.scripted" />
        </label>
        {!apiBase && (
          <label>
            <input
              type="radio"
              checked={mode === "anthropic"}
              onChange={() => setMode("anthropic")}
              disabled={!info.has_api_key}
            />{" "}
            <Tx k="live.anthropic" />
            {!info.has_api_key && <Tx k="live.noKey" />}
          </label>
        )}
        {mode === "scripted" ? (
          <>
            <select value={demo} onChange={(e) => setDemo(e.target.value)}>
              {info.demos.map((d) => (
                <option key={d.id} value={d.id}>
                  {titleText(lang, `demo/${d.id}`, d.title)}
                </option>
              ))}
            </select>
            {selected && <Question text={selected.question} />}
            <Tx k="live.scriptedNote" as="p" />
          </>
        ) : (
          <>
            <select value={domain} onChange={(e) => setDomain(e.target.value)}>
              {info.domains.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
            {domain === "mushoku" && (
              <label>
                <Tx k="live.progress" />{" "}
                <input
                  value={progress}
                  onChange={(e) => setProgress(e.target.value)}
                  maxLength={40}
                  placeholder="novel:5 / anime:2-12"
                />
              </label>
            )}
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={4}
              placeholder={t("live.placeholder")}
              maxLength={2000}
            />
          </>
        )}
        {!apiBase && (
          <label>
            <input type="checkbox" checked={fake} onChange={(e) => setFake(e.target.checked)} /> <Tx k="live.fake" />
          </label>
        )}
        {!info.ocr && <Tx k="live.noOcr" as="p" />}
        <button onClick={submit} disabled={busy || (mode !== "scripted" && !question.trim())}>
          {statusText ? statusText : <Tx k={busy ? "live.running" : "live.run"} />}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {run && <RunPlayer run={run} services={services} />}
    </main>
  );
}
