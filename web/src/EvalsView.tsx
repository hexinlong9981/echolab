import { useState } from "react";
import { CaseNotes } from "./CaseNotes";
import { useI18n } from "./i18n";
import { Title, Tx } from "./Tx";
import type { DataIndex } from "./types";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export function EvalsView({ index, onOpen }: { index: DataIndex; onOpen: (runId: string) => void }) {
  const { lang } = useI18n();
  // 説明を開いているケース（「<評価>/<ケース ID>」）
  const [openNotes, setOpenNotes] = useState<Set<string>>(() => new Set());
  const toggleNotes = (key: string) =>
    setOpenNotes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  return (
    <main className="evals pad">
      <Tx k="evals.intro" as="p" />
      <div className="cards">
        {index.suites.map((s) => (
          <section key={s.id} className={`card ${s.ok ? "" : "bad"}`}>
            <h2>
              <Title k={`suite/${s.id}`} ja={s.title} />
            </h2>
            <dl>
              <dt>
                <Tx k="metric.faithfulness" />
              </dt>
              <dd className={s.faithfulness === 1 ? "ok" : "bad"}>{s.faithfulness.toFixed(3)}</dd>
              <dt>
                <Tx k="metric.passed" />
              </dt>
              <dd>
                {s.passed} / {s.total}
              </dd>
              <dt>
                <Tx k="metric.rejection" />
              </dt>
              <dd>{pct(s.draft_rejection_rate)}</dd>
              <dt>
                <Tx k="metric.toolErrors" />
              </dt>
              <dd>{s.tool_errors}</dd>
            </dl>
          </section>
        ))}
      </div>
      {index.suites.map((s) => (
        <section key={s.id}>
          <h2>
            <Title k={`suite/${s.id}`} ja={s.title} />
            <Tx k="evals.domain" p={{ domain: s.domain }} />
          </h2>
          <table className="cases">
            <thead>
              <tr>
                <th>
                  <Tx k="col.case" />
                </th>
                <th>
                  <Tx k="col.status" />
                </th>
                <th>
                  <Tx k="col.drafts" />
                </th>
                <th>
                  <Tx k="col.rejected" />
                </th>
                <th>
                  <Tx k="col.refused" />
                </th>
                <th>
                  <Tx k="col.result" />
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {s.cases.flatMap((c) => {
                const noteKey = `${s.id}/${c.id}`;
                const opened = openNotes.has(noteKey);
                return [
                <tr key={c.id}>
                  <td>
                    <code>{c.id}</code>
                    <div className="muted">
                      <Title k={`${s.id}/${c.id}`} ja={c.title} />
                    </div>
                  </td>
                  <td>{c.status}</td>
                  <td className="num">{c.drafts}</td>
                  <td className="num">{c.drafts_rejected}</td>
                  <td className="num">{c.tool_errors}</td>
                  <td className={c.passed ? "ok" : "bad"}>
                    <Tx k={c.passed ? "passed" : "failed"} />
                    {/* 不合格の理由はプログラムの出力（日本語のまま） */}
                    {!c.passed && <span lang="ja">{`${lang === "ja" ? "：" : ": "}${c.failures.join("；")}`}</span>}
                  </td>
                  <td className="actions">
                    <button className={`notes-toggle ${opened ? "open" : ""}`} aria-expanded={opened} onClick={() => toggleNotes(noteKey)}>
                      <span className="caret" aria-hidden="true" />
                      <Tx k="note.toggle" />
                    </button>
                    {c.key && (
                      <button onClick={() => onOpen(c.key as string)}>
                        <Tx k="btn.replay" />
                      </button>
                    )}
                  </td>
                </tr>,
                opened && (
                  <tr key={`${c.id}-notes`} className="notes-row">
                    <td colSpan={7}>
                      <CaseNotes noteKey={noteKey} summary={c} collapsible={false} />
                    </td>
                  </tr>
                ),
                ];
              })}
            </tbody>
          </table>
        </section>
      ))}
    </main>
  );
}
