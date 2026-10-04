import { useEffect, useMemo, useState } from "react";
import { FlowDiagram } from "./FlowDiagram";
import { useI18n } from "./i18n";
import { buildSteps } from "./replay";
import { Tx } from "./Tx";
import type { RunRecord } from "./types";

/** 1 回の実行を、図・コマ送り・出典の表で見せる。公開の回放と手元の実行で共用する。 */
export function RunPlayer({
  run,
  services,
  initialStep = 0,
}: {
  run: RunRecord;
  services: Record<string, string>;
  /** 最初に見せるコマ（0 から。URL の #replay/<実行 ID>/<コマ> で指定できる） */
  initialStep?: number;
}) {
  const { h } = useI18n();
  const steps = useMemo(() => buildSteps(run.events, services, h), [run, services, h]);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setI(Math.min(initialStep, Math.max(0, steps.length - 1)));
    setPlaying(false);
  }, [run, initialStep, steps.length]);

  useEffect(() => {
    if (!playing) return;
    if (i >= steps.length - 1) {
      setPlaying(false);
      return;
    }
    const t = window.setTimeout(() => setI((n) => n + 1), 1400);
    return () => window.clearTimeout(t);
  }, [playing, i, steps.length]);

  const step = steps[i];
  const question = run.events.find((e) => e.event === "question");
  const answer = run.events.find((e) => e.event === "answer");
  const atEnd = i === steps.length - 1;

  return (
    <div className="player">
      {question?.event === "question" && <p className="question">Q. {question.question}</p>}
      <div className="badges">
        <Tx k="badge.domain" p={{ domain: run.domain ?? "" }} />
        {run.llm === "ScriptedLLM" ? <Tx k="badge.scripted" /> : <span>{run.llm}</span>}
        <Tx k={run.fake_backend ? "badge.fake" : "badge.real"} />
        <Tx k="badge.status" p={{ status: run.status ?? "" }} className={run.status === "answered" ? "ok" : "bad"} />
      </div>
      <FlowDiagram step={step} />
      <div className="controls">
        <button onClick={() => setI(0)} disabled={i === 0}>
          <Tx k="btn.first" />
        </button>
        <button onClick={() => setI((n) => Math.max(0, n - 1))} disabled={i === 0}>
          <Tx k="btn.prev" />
        </button>
        <button onClick={() => setPlaying((p) => !p)} disabled={atEnd && !playing}>
          <Tx k={playing ? "btn.pause" : "btn.play"} />
        </button>
        <button onClick={() => setI((n) => Math.min(steps.length - 1, n + 1))} disabled={atEnd}>
          <Tx k="btn.next" />
        </button>
        <span className="muted">
          {i + 1} / {steps.length}
        </span>
      </div>
      {step && (
        <div className={`step ${Object.values(step.nodes).includes("bad") ? "bad" : ""}`}>
          <h3 dangerouslySetInnerHTML={{ __html: step.title }} />
          <p dangerouslySetInnerHTML={{ __html: step.detail }} />
          <details>
            <summary>
              <Tx k="step.json" />
            </summary>
            <pre>{JSON.stringify(step.event, null, 1)}</pre>
          </details>
        </div>
      )}
      {step && step.sources.length > 0 && (
        <table className="sources">
          <thead>
            <tr>
              <th>
                <Tx k="col.source" />
              </th>
              <th>
                <Tx k="col.value" />
              </th>
              <th>
                <Tx k="col.tool" />
              </th>
            </tr>
          </thead>
          <tbody>
            {step.sources.map((s) => (
              <tr key={s.source_id}>
                <td>
                  <code>{s.source_id}</code>
                </td>
                <td className="num">{s.value}</td>
                <td>{s.tool}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {atEnd && answer?.event === "answer" && <pre className="answer">{answer.answer}</pre>}
    </div>
  );
}
