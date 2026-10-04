import { useState } from "react";
import { type AskRequest, ask } from "./data";
import { type Lang, PACK_ORDER, domainTitle, titleText, useI18n } from "./i18n";
import { LiveError, askOnServer, wake } from "./liveApi";
import { Question } from "./Question";
import { RunPlayer } from "./RunPlayer";
import { Tx } from "./Tx";
import type { LocalInfo, RunRecord } from "./types";

const SAMPLES: Record<string, { label: Record<Lang, string>; text: string; progress?: string }[]> = {
  wuwa: [
    {
      label: { zh: "填入示例：配装期望伤害", ja: "入力例：期待ダメージ計算", en: "Sample: Expected Damage" },
      text: "攻撃力 2000、スキル倍率 2.5、ダメージバフ 0.3、会心率 0.6、会心ダメージ 2.2、防御定数 1600、敵の防御 1000、防御無視 0、敵の耐性 0.1、耐性ダウン 0 のときの期待ダメージは？",
    },
  ],
  mushoku: [
    {
      label: { zh: "填入示例：转移事件时年龄", ja: "入力例：転移事件時の年齢", en: "Sample: Age at Displacement" },
      text: "ルーデウスの転移事件時の年齢は？",
      progress: "novel:3",
    },
    {
      label: { zh: "填入示例：布耶纳村到罗亚行程", ja: "入力例：ブエナ村からロアの日数", en: "Sample: Buena to Roa route" },
      text: "ブエナ村からロアまでの移動にかかる日数は？",
      progress: "novel:5",
    },
  ],
  mortgage: [
    {
      label: { zh: "填入示例：等额本息与等额本金利息差", ja: "入力例：元利均等と元金均等の比較", en: "Sample: Equal payment vs principal" },
      text: "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？",
    },
    {
      label: { zh: "填入示例：提前还款比较", ja: "入力例：繰り上げ返済の比較", en: "Sample: Prepayment comparison" },
      text: "借入 3000 万円、年利 1.5%、35 年で 5 年後に 200 万円を繰り上げ返済するとき、期間短縮型と返済額軽減型で利息軽減額の違いは？",
    },
  ],
};

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
  // サーバ接続時は既定で gemini、手元は scripted
  const [mode, setMode] = useState<"scripted" | "gemini" | "anthropic">(apiBase ? "gemini" : "scripted");
  const [demo, setDemo] = useState(info.demos[0]?.id ?? "");
  const [question, setQuestion] = useState("");
  const orderedDomains = [...info.domains].sort((a, b) => {
    const ia = PACK_ORDER.indexOf(a);
    const ib = PACK_ORDER.indexOf(b);
    return (ia >= 0 ? ia : 99) - (ib >= 0 ? ib : 99);
  });
  const [domain, setDomain] = useState(orderedDomains[0] ?? "wuwa");
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
              {orderedDomains.map((d) => (
                <option key={d} value={d}>
                  {domainTitle(lang, d)}
                </option>
              ))}
            </select>
            {SAMPLES[domain] && (
              <div className="samples">
                {SAMPLES[domain].map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="sample-chip"
                    onClick={() => {
                      setQuestion(s.text);
                      if (s.progress) setProgress(s.progress);
                    }}
                  >
                    {s.label[lang] ?? s.label.zh}
                  </button>
                ))}
              </div>
            )}
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
