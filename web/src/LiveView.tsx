import { useState } from "react";
import { type AskRequest, ask } from "./data";
import { RunPlayer } from "./RunPlayer";
import type { LocalInfo, RunRecord } from "./types";

/** 手元の API（python -m servers.web_api）につないだときだけ出る「実行」画面。公開のサイトには出ない。 */
export function LiveView({ info, services }: { info: LocalInfo; services: Record<string, string> }) {
  const [mode, setMode] = useState<"scripted" | "anthropic">("scripted");
  const [demo, setDemo] = useState(info.demos[0]?.id ?? "");
  const [question, setQuestion] = useState("");
  const [domain, setDomain] = useState(info.domains.includes("wuwa") ? "wuwa" : (info.domains[0] ?? ""));
  const [fake, setFake] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);

  const submit = async () => {
    const req: AskRequest =
      mode === "scripted" ? { llm: "scripted", demo, fake_backend: fake } : { llm: "anthropic", question, domain, fake_backend: fake };
    setBusy(true);
    setError(null);
    try {
      setRun(await ask(req));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const selected = info.demos.find((d) => d.id === demo);

  return (
    <main className="live pad">
      <p className="muted">
        この画面は手元の API（127.0.0.1）だけで動きます。実物の Claude はコストの上限（日次 {info.caps_usd.daily} USD・月次{" "}
        {info.caps_usd.monthly} USD）に従います。
      </p>
      <div className="form">
        <label>
          <input type="radio" checked={mode === "scripted"} onChange={() => setMode("scripted")} /> 台本のデモ（API キー不要）
        </label>
        <label>
          <input type="radio" checked={mode === "anthropic"} onChange={() => setMode("anthropic")} disabled={!info.has_api_key} />{" "}
          実物の Claude{info.has_api_key ? "" : "（ANTHROPIC_API_KEY が未設定）"}
        </label>
        {mode === "scripted" ? (
          <>
            <select value={demo} onChange={(e) => setDemo(e.target.value)}>
              {info.demos.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
            {selected && <p className="question">Q. {selected.question}</p>}
            <p className="muted">台本モードは質問の中身を読まず、台本を順に再生します（再現のための仕組みです）。</p>
          </>
        ) : (
          <>
            <select value={domain} onChange={(e) => setDomain(e.target.value)}>
              {info.domains.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={4} placeholder="質問（日本語）" maxLength={2000} />
          </>
        )}
        <label>
          <input type="checkbox" checked={fake} onChange={(e) => setFake(e.target.checked)} /> 試験用の計算サービスを使う（Java・Tesseract
          不要）
        </label>
        {!info.ocr && <p className="muted">Tesseract が見つからないため、実物の OCR は使えません。</p>}
        <button onClick={submit} disabled={busy || (mode === "anthropic" && !question.trim())}>
          {busy ? "実行中…" : "実行する"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {run && <RunPlayer run={run} services={services} />}
    </main>
  );
}
