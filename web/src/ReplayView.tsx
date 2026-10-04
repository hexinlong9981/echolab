import { useEffect, useState } from "react";
import { loadRun } from "./data";
import { RunPlayer } from "./RunPlayer";
import type { DataIndex, RunRecord } from "./types";

export function ReplayView({
  index,
  runId,
  step,
  onSelect,
}: {
  index: DataIndex;
  runId: string | null;
  step: number;
  onSelect: (runId: string) => void;
}) {
  const current = runId ?? index.demos[0]?.run_id ?? null;
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setError(null);
    loadRun(current).then(setRun, (e: Error) => setError(e.message));
  }, [current]);

  return (
    <main className="replay">
      <aside className="list">
        <h2>デモ</h2>
        <ul>
          {index.demos.map((d) => (
            <li key={d.id}>
              <button className={d.run_id === current ? "on" : ""} onClick={() => onSelect(d.run_id)}>
                {d.title}
              </button>
            </li>
          ))}
        </ul>
        {index.suites.map((s) => (
          <section key={s.id}>
            <h2>評価：{s.title}</h2>
            <ul>
              {s.cases.map(
                (c) =>
                  c.run_id && (
                    <li key={c.id}>
                      <button className={c.run_id === current ? "on" : ""} onClick={() => onSelect(c.run_id as string)}>
                        <span className={c.passed ? "dot ok" : "dot bad"} aria-label={c.passed ? "合格" : "不合格"} />
                        {c.title}
                      </button>
                    </li>
                  ),
              )}
            </ul>
          </section>
        ))}
      </aside>
      <section className="stage">
        {error && <p className="error">{error}</p>}
        {run && run.run_id === current && <RunPlayer run={run} services={index.services} initialStep={step} />}
      </section>
    </main>
  );
}
