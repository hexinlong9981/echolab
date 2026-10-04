import { useEffect, useState } from "react";
import { loadIndex, loadLocalInfo } from "./data";
import { EvalsView } from "./EvalsView";
import { LiveView } from "./LiveView";
import { ReplayView } from "./ReplayView";
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

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    loadIndex().then(setIndex, (e: Error) => setError(e.message));
    void loadLocalInfo().then(setLocal);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (hash: string) => {
    window.location.hash = hash;
  };

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <strong>EchoLab</strong>
          <span>AI に計算させない AI アシスタント</span>
        </div>
        <nav className="tabs">
          <button className={route.tab === "replay" ? "on" : ""} onClick={() => go("replay")}>
            回放
          </button>
          <button className={route.tab === "evals" ? "on" : ""} onClick={() => go("evals")}>
            評価
          </button>
          {local && (
            <button className={route.tab === "live" ? "on" : ""} onClick={() => go("live")}>
              実行（手元）
            </button>
          )}
        </nav>
        <a className="repo" href="https://github.com/hexinlong9981/echolab" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </header>
      {error && <p className="error">{error}</p>}
      {!index && !error && <p className="muted pad">読み込み中…</p>}
      {index && route.tab === "replay" && <ReplayView index={index} runId={route.runId} step={route.step} onSelect={(id) => go(`replay/${id}`)} />}
      {index && route.tab === "evals" && <EvalsView index={index} onOpen={(id) => go(`replay/${id}`)} />}
      {index && route.tab === "live" && local && <LiveView info={local} services={index.services} />}
      {index && route.tab === "live" && !local && (
        <p className="muted pad">「実行」は手元の API（python -m servers.web_api）から開いたときだけ使えます。</p>
      )}
      <footer className="foot">
        台本モード（API キー不要）で CI が生成した記録の回放です。数値は決定的なツールが計算し、LLM は書きません。
        {index && <> データ生成 {index.generated_at}{index.commit ? `・コミット ${index.commit.slice(0, 7)}` : ""}。</>}
        『鳴潮』の非公式ファン作品。住宅ローンは計算例で、金融上の助言ではありません。
      </footer>
    </div>
  );
}
