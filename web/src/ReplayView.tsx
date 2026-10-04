import { useEffect, useState } from "react";
import { DataMissingError, loadRun } from "./data";
import { DEMOS_GROUP, groupOf, toggleGroup } from "./listGroups";
import { CaseNotes } from "./CaseNotes";
import { RunPlayer } from "./RunPlayer";
import { Title, Tx } from "./Tx";
import type { DataIndex, RunRecord } from "./types";

export function ReplayView({
  index,
  runId,
  step,
  onSelect,
  onStale,
}: {
  index: DataIndex;
  runId: string | null;
  step: number;
  onSelect: (runId: string) => void;
  /** 記録が見つからないとき、一覧を読み直す（公開し直された可能性がある） */
  onStale: () => Promise<DataIndex>;
}) {
  const current = runId ?? index.demos[0]?.key ?? null;
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  // 開いている分組は 1 つだけ（アコーディオン）。選んだ実行が変わったら、その分組を開く
  const [open, setOpen] = useState<string | null>(() => groupOf(index, current));
  useEffect(() => {
    setOpen(groupOf(index, current));
  }, [index, current]);

  useEffect(() => {
    if (!current) return;
    let cancelled = false;
    setError(null);
    setMissing(false);
    (async () => {
      try {
        const r = await loadRun(current);
        if (!cancelled) setRun(r);
      } catch (e) {
        if (!(e instanceof DataMissingError)) {
          if (!cancelled) setError((e as Error).message);
          return;
        }
        // 公開し直されたかもしれない：一覧を 1 回だけ読み直してから、もう一度読む
        try {
          await onStale();
          const r = await loadRun(current);
          if (!cancelled) setRun(r);
        } catch {
          if (!cancelled) setMissing(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // onStale は App の再描画ごとに作り直されるので、依存に入れない
  }, [current]);

  // 選んだのが評価のケースなら、その説明を図の上に出す
  const selectedCase = (() => {
    for (const s of index.suites) {
      const c = s.cases.find((x) => x.key === current);
      if (c) return { noteKey: `${s.id}/${c.id}`, summary: c };
    }
    return null;
  })();

  return (
    <main className="replay">
      <aside className="list">
        <section className={`group ${open === DEMOS_GROUP ? "open" : ""}`}>
          <button className="group-head" aria-expanded={open === DEMOS_GROUP} onClick={() => setOpen((o) => toggleGroup(o, DEMOS_GROUP))}>
            <span className="caret" aria-hidden="true" />
            <Tx k="list.demos" />
          </button>
          {open === DEMOS_GROUP && (
            <ul>
              {index.demos.map((d) => (
                <li key={d.id}>
                  <button className={d.key === current ? "on" : ""} onClick={() => onSelect(d.key)}>
                    <Title k={`demo/${d.id}`} ja={d.title} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        {index.suites.map((s) => (
          <section key={s.id} className={`group ${open === s.id ? "open" : ""}`}>
            <button className="group-head" aria-expanded={open === s.id} onClick={() => setOpen((o) => toggleGroup(o, s.id))}>
              <span className="caret" aria-hidden="true" />
              <span>
                <Tx k="list.suitePrefix" />
                <Title k={`suite/${s.id}`} ja={s.title} />
              </span>
            </button>
            {open === s.id && (
              <ul>
                {s.cases.map(
                  (c) =>
                    c.key && (
                      <li key={c.id}>
                        <button className={c.key === current ? "on" : ""} onClick={() => onSelect(c.key as string)}>
                          <span className={c.passed ? "dot ok" : "dot bad"} />
                          <Title k={`${s.id}/${c.id}`} ja={c.title} />
                        </button>
                      </li>
                    ),
                )}
              </ul>
            )}
          </section>
        ))}
      </aside>
      <section className="stage">
        {error && <p className="error">{error}</p>}
        {missing && (
          <div className="error">
            <Tx k="data.missing" />{" "}
            {index.demos[0] && (
              <button onClick={() => onSelect(index.demos[0]?.key as string)}>
                <Tx k="data.toFirst" />
              </button>
            )}
          </div>
        )}
        {selectedCase && (
          <CaseNotes key={selectedCase.noteKey} noteKey={selectedCase.noteKey} summary={selectedCase.summary} />
        )}
        {run && run.key === current && <RunPlayer run={run} services={index.services} initialStep={step} />}
      </section>
    </main>
  );
}
