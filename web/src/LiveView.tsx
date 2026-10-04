import { useEffect, useState } from "react";
import { type AskRequest, ask } from "./data";
import { type Lang, PACK_ORDER, domainTitle, useI18n } from "./i18n";
import { LiveError, askOnServer, wake } from "./liveApi";
import { RunPlayer } from "./RunPlayer";
import { Tx } from "./Tx";
import type { LocalInfo, RunRecord } from "./types";

interface SampleItem {
  label: Record<Lang, string>;
  text: Record<Lang, string>;
  progress?: string;
}

const SAMPLES: Record<string, SampleItem[]> = {
  wuwa: [
    {
      label: { zh: "填入示例：配装期望伤害", ja: "入力例：期待ダメージ計算", en: "Sample: Expected Damage" },
      text: {
        zh: "攻击力2000，技能倍率2.5，伤害加成0.3，暴击率0.6，暴击伤害2.2，防御常数1600，敌人防御1000，防御穿透0，敌人抗性0.1，抗性降低0，此时的期望伤害是多少？",
        ja: "攻撃力 2000、スキル倍率 2.5、ダメージバフ 0.3、会心率 0.6、会心ダメージ 2.2、防御定数 1600、敵の防御 1000、防御無視 0、敵の耐性 0.1、耐性ダウン 0 のときの期待ダメージは？",
        en: "What is the expected damage when attack is 2000, skill multiplier is 2.5, damage bonus is 0.3, crit rate is 0.6, crit damage is 2.2, defense constant is 1600, enemy defense is 1000, and enemy resistance is 0.1?",
      },
    },
  ],
  mushoku: [
    {
      label: { zh: "填入示例：转移事件时年龄", ja: "入力例：転移事件時の年齢", en: "Sample: Age at Displacement" },
      text: {
        zh: "鲁迪乌斯在转移事件发生时几岁？",
        ja: "ルーデウスの転移事件時の年齢は？",
        en: "How old was Rudeus at the time of the Displacement Incident?",
      },
      progress: "novel:3",
    },
    {
      label: { zh: "填入示例：布耶纳村到罗亚行程", ja: "入力例：ブエナ村からロアの日数", en: "Sample: Buena to Roa route" },
      text: {
        zh: "从布耶纳村到罗亚移动需要多少天？",
        ja: "ブエナ村からロアまでの移動にかかる日数は？",
        en: "How many days does it take to travel from Buena Village to Roa?",
      },
      progress: "novel:5",
    },
  ],
  mortgage: [
    {
      label: { zh: "填入示例：等额本息与等额本金利息差", ja: "入力例：元利均等と元金均等の比較", en: "Sample: Equal payment vs principal" },
      text: {
        zh: "贷款 3000 万日元，年利率 1.5%，期限 35 年，等额本息和等额本金的总利息差多少？",
        ja: "3000 万円を年 1.5%、35 年で借りるとき、元利均等と元金均等では利息の合計はどれだけ違う？",
        en: "Borrowing 30 million yen at 1.5% annual interest for 35 years, what is the difference in total interest between equal payment and equal principal?",
      },
    },
    {
      label: { zh: "填入示例：提前还款比较", ja: "入力例：繰り上げ返済の比較", en: "Sample: Prepayment comparison" },
      text: {
        zh: "贷款 3000 万日元，年利率 1.5%，期限 35 年，在 5 年后提前还款 200 万日元，缩短期限型和减少月供型能节省多少利息？",
        ja: "借入 3000 万円、年利 1.5%、35 年で 5 年後に 200 万円を繰り上げ返済するとき、期間短縮型と返済額軽減型で利息軽減額の違いは？",
        en: "Borrowing 30 million yen at 1.5% for 35 years and prepaying 2 million yen after 5 years, what is the difference in interest saved between shortening the term and reducing monthly payments?",
      },
    },
  ],
};

/** リアルタイム対話・実行画面（Vertex AI Gemini・実物の計算サービス）。 */
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

  // 认证状态控制（仅针对公网服务器访问，本地直接免密）
  const [authed, setAuthed] = useState(!apiBase);
  const [authChecking, setAuthChecking] = useState(Boolean(apiBase));
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  useEffect(() => {
    if (!apiBase) return;
    fetch("/__auth", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: { authenticated?: boolean; configured?: boolean }) => {
        setAuthed(Boolean(data.authenticated || data.configured === false));
      })
      .catch(() => {
        setAuthed(false);
      })
      .finally(() => {
        setAuthChecking(false);
      });
  }, [apiBase]);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthBusy(true);
    setAuthError(null);
    try {
      const res = await fetch("/__login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: authPassword }),
      });
      const data = (await res.json()) as { ok?: boolean };
      if (res.ok && data.ok) {
        setAuthed(true);
      } else {
        setAuthError(t("live.authWrong"));
      }
    } catch {
      setAuthError(t("live.authWrong"));
    } finally {
      setAuthBusy(false);
    }
  };

  const [mode, setMode] = useState<"gemini" | "anthropic">("gemini");
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
    const req: AskRequest = {
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

  if (authChecking) {
    return (
      <main className="live pad">
        <p className="muted">
          <Tx k="loading" />
        </p>
      </main>
    );
  }

  if (!authed) {
    return (
      <main className="live pad">
        <div className="card" style={{ maxWidth: 360, margin: "40px auto", textAlign: "center" }}>
          <h2>
            <Tx k="live.authTitle" />
          </h2>
          <p className="muted" style={{ fontSize: "0.86em", lineHeight: 1.5, margin: "8px 0 16px" }}>
            <Tx k="live.authDesc" />
          </p>
          {authError && (
            <p className="error" style={{ marginBottom: 12 }}>
              {authError}
            </p>
          )}
          <form onSubmit={handleUnlock} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input
              type="password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              placeholder={t("live.authPlaceholder")}
              autoFocus
              required
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "8px 10px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--bg)",
                color: "var(--text)",
              }}
            />
            <button
              type="submit"
              disabled={authBusy}
              style={{
                padding: "8px 12px",
                border: "1px solid var(--accent)",
                color: "var(--accent)",
                borderRadius: 6,
                background: "transparent",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {authBusy ? t("live.running") : <Tx k="live.authUnlock" />}
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="live pad">
      <p className="muted">
        <Tx k="live.intro" p={{ daily: info.caps_usd.daily, monthly: info.caps_usd.monthly }} />
      </p>
      <div className="form">
        {!apiBase && info.has_api_key && (
          <div style={{ display: "flex", gap: "14px", marginBottom: "4px" }}>
            <label>
              <input type="radio" checked={mode === "gemini"} onChange={() => setMode("gemini")} /> <Tx k="live.gemini" />
            </label>
            <label>
              <input type="radio" checked={mode === "anthropic"} onChange={() => setMode("anthropic")} /> <Tx k="live.anthropic" />
            </label>
          </div>
        )}
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
                  setQuestion(s.text[lang] ?? s.text.zh);
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
        {!apiBase && (
          <label>
            <input type="checkbox" checked={fake} onChange={(e) => setFake(e.target.checked)} /> <Tx k="live.fake" />
          </label>
        )}
        {!info.ocr && <Tx k="live.noOcr" as="p" />}
        <button onClick={submit} disabled={busy || !question.trim()}>
          {statusText ? statusText : <Tx k={busy ? "live.running" : "live.run"} />}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {run && <RunPlayer run={run} services={services} />}
    </main>
  );
}
