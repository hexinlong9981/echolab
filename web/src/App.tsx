import { useEffect, useMemo, useState } from "react";
import { forgetRuns, loadIndex, loadLocalInfo } from "./data";
import { EvalsView } from "./EvalsView";
import { detectLang, LANGS, type Lang, LangContext, loadRubyPrefs, makeI18n, store } from "./i18n";
import { liveApiBase } from "./liveApi";
import { LiveView } from "./LiveView";
import { ReplayView } from "./ReplayView";
import { Tx } from "./Tx";
import type { DataIndex, LocalInfo } from "./types";

type Tab = "replay" | "evals" | "live";

/** URL のハッシュ（#replay/<実行 ID>[/<コマ>]・#evals・#live）で画面を選ぶ。ルータの依存は使わない。 */
function readHash(): { tab: Tab; runId: string | null; step: number } {
  const [tab, runId, step] = window.location.hash.replace(/^#/, "").split("/");
  if (tab === "evals" || tab === "live") return { tab, runId: null, step: 0 };
  const n = Number(step);
  return {
    tab: "replay",
    runId: runId ? decodeURIComponent(runId) : null,
    step: Number.isInteger(n) && n > 0 ? n - 1 : 0,
  };
}

export function App() {
  const [route, setRoute] = useState(readHash);
  const [index, setIndex] = useState<DataIndex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [local, setLocal] = useState<LocalInfo | null>(null);
  const [lang, setLang] = useState<Lang>(detectLang);
  const [ruby, setRuby] = useState(loadRubyPrefs);
  const i18n = useMemo(() => makeI18n(lang), [lang]);
  const liveBase = useMemo(() => liveApiBase(), []);

  const serverInfo = useMemo<LocalInfo | null>(() => {
    if (local) return local;
    if (index) {
      return {
        domains: ["wuwa", "mushoku", "mortgage"],
        demos: index.demos.map((d) => ({
          id: d.id,
          title: d.title,
          question: d.question,
          domain: d.domain,
          script: d.script,
        })),
        has_api_key: true,
        caps_usd: { daily: "1.00", monthly: "10.00" },
        ocr: true,
      };
    }
    return null;
  }, [local, index]);

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    loadIndex().then(setIndex, (e: Error) => setError(e.message));
    void loadLocalInfo().then(setLocal);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.documentElement.lang = LANGS.find((l) => l.code === lang)?.html ?? "ja";
    document.title = i18n.t("doc.title");
  }, [lang, i18n]);

  /** 公開し直されたデータに合わせて一覧を読み直す（記録が見つからなかったとき）。 */
  const refreshIndex = async () => {
    forgetRuns();
    const fresh = await loadIndex();
    setIndex(fresh);
    return fresh;
  };

  const go = (hash: string) => {
    window.location.hash = hash;
  };
  const chooseLang = (l: Lang) => {
    setLang(l);
    store("echolab-lang", l);
  };
  const toggle = (kind: "furi" | "eng") => {
    const next = { ...ruby, [kind]: !ruby[kind] };
    setRuby(next);
    store(`echolab-${kind}`, next[kind] ? "on" : "off");
  };

  const rootClass = ["app", ruby.furi ? "" : "no-furi", ruby.eng ? "" : "no-eng"].join(" ").trim();

  return (
    <LangContext.Provider value={i18n}>
      <div className={rootClass}>
        <header className="top">
          <div className="brand">
            <strong>EchoLab</strong>
            <Tx k="tagline" />
          </div>
          <nav className="tabs">
            <button className={route.tab === "replay" ? "on" : ""} onClick={() => go("replay")}>
              <Tx k="tab.replay" />
            </button>
            <button className={route.tab === "evals" ? "on" : ""} onClick={() => go("evals")}>
              <Tx k="tab.evals" />
            </button>
            <button className={route.tab === "live" ? "on" : ""} onClick={() => go("live")}>
              <Tx k="tab.live" />
            </button>
          </nav>
          <div className="prefs">
            <span className="langs" role="group" aria-label="Language / 言語 / 语言">
              {LANGS.map((l) => (
                <button key={l.code} className={l.code === lang ? "on" : ""} onClick={() => chooseLang(l.code)} lang={l.html}>
                  {l.label}
                </button>
              ))}
            </span>
            {lang === "ja" && (
              <span className="ruby-toggles">
                <button className={ruby.furi ? "on" : ""} onClick={() => toggle("furi")} aria-pressed={ruby.furi}>
                  ふりがな：{ruby.furi ? "あり" : "なし"}
                </button>
                <button className={ruby.eng ? "on" : ""} onClick={() => toggle("eng")} aria-pressed={ruby.eng}>
                  英語：{ruby.eng ? "あり" : "なし"}
                </button>
              </span>
            )}
            <a className="repo" href="https://github.com/hexinlong9981/echolab" target="_blank" rel="noreferrer">
              GitHub
            </a>
          </div>
        </header>
        {error && <p className="error">{error}</p>}
        {!index && !error && <Tx k="loading" as="p" />}
        {index && route.tab === "replay" && (
          <ReplayView
            index={index}
            runId={route.runId}
            step={route.step}
            onSelect={(id) => go(`replay/${id}`)}
            onStale={refreshIndex}
          />
        )}
        {index && route.tab === "evals" && <EvalsView index={index} onOpen={(id) => go(`replay/${id}`)} />}
        {index && route.tab === "live" && serverInfo && (
          <LiveView info={serverInfo} services={index.services} apiBase={local ? undefined : liveBase} />
        )}
        {index && route.tab === "live" && !serverInfo && <Tx k="live.unavailable" as="p" />}
        <footer className="foot">
          {route.tab === "live" ? (
            <>
              <Tx k="foot.live" />{" "}
            </>
          ) : (
            <>
              <Tx k="foot.main" />{" "}
              {index && (
                <>
                  <Tx k="foot.generated" p={{ at: index.generated_at }} />
                  {index.commit && <Tx k="foot.commit" p={{ sha: index.commit.slice(0, 7) }} />}
                  {lang === "ja" ? "。" : ". "}
                </>
              )}
            </>
          )}
          <Tx k="foot.legal" /> {lang !== "ja" && <Tx k="foot.content" />}
        </footer>
      </div>
    </LangContext.Provider>
  );
}
