import { useEffect, useMemo, useState } from "react";
import { FlowDiagram } from "./FlowDiagram";
import { useI18n } from "./i18n";
import { buildSteps } from "./replay";
import { OutputTranslation } from "./OutputTranslation";
import { Question } from "./Question";
import { Tx } from "./Tx";
import type { RunRecord, TraceRecord } from "./types";

/** 1 回の実行を、図・コマ送り・出典の表で見せる。公開の回放と手元の実行で共用する。 */
export function RunPlayer({
  run,
  services,
  initialStep,
  followLatest = false,
  isLive = false,
}: {
  run: RunRecord;
  services: Record<string, string>;
  /** 最初に見せるコマ（0 から。URL の #replay/<実行 ID>/<コマ> で指定できる） */
  initialStep?: number;
  /** 新しいステップが追加されたとき最新のステップを追従するか */
  followLatest?: boolean;
  /** リアルタイム対話（多言語直接出力）かどうか。true の場合は静的翻訳注記や lang="ja" を無効化する */
  isLive?: boolean;
}) {
  const { h, lang } = useI18n();
  const steps = useMemo(() => buildSteps(run.events, services, h), [run, services, h]);
  const [i, setI] = useState(() => (initialStep !== undefined ? initialStep : Math.max(0, steps.length - 1)));
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (followLatest || initialStep === undefined) {
      setI(Math.max(0, steps.length - 1));
      setPlaying(false);
    } else {
      setI(Math.min(initialStep, Math.max(0, steps.length - 1)));
      setPlaying(false);
    }
  }, [run.run_id, initialStep, steps.length, followLatest]);

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
      {question?.event === "question" && <Question text={question.question} />}
      <div className="badges">
        <Tx k="badge.domain" p={{ domain: run.domain ?? "" }} />
        {run.context?.progress && <Tx k="badge.progress" p={{ progress: run.context.progress }} />}
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
          {!isLive && <OutputTranslation texts={rawTexts(step.event)} />}
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
      {atEnd && answer?.event === "answer" && (
        <>
          <pre className="answer" lang={isLive ? undefined : "ja"}>
            {answer.answer}
          </pre>
          {!isLive && lang !== "ja" && <Tx k="answer.note" as="p" />}
          {!isLive && <OutputTranslation texts={[answer.answer]} />}
        </>
      )}
    </div>
  );
}

/** コマの補足に出す、記録の中身（プログラムの出力）の文。参考訳の対象。 */
function rawTexts(event: TraceRecord): string[] {
  switch (event.event) {
    case "verdict":
      return event.ok ? [] : event.problems;
    case "tool_result":
      return event.outcome.error ? [event.outcome.error] : [];
    case "llm_error":
      return [event.error];
    case "budget_exceeded":
      return [event.reason];
    default:
      return [];
  }
}
