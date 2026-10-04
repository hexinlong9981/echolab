import { resultHtml } from "./caseNotes";
import { caseNoteHtml, useI18n } from "./i18n";
import { Tx } from "./Tx";
import type { CaseSummary } from "./types";

/** 評価ケースの説明：内容・用意・結果・評価（結果は実行のデータから作る）。 */
export function CaseNotes({ noteKey, summary, collapsible = true }: { noteKey: string; summary: CaseSummary; collapsible?: boolean }) {
  const { lang, h } = useI18n();
  const note = caseNoteHtml(lang, noteKey);
  if (!note) return null;
  const rows: [string, string][] = [
    ["note.content", note.content],
    ["note.purpose", note.purpose],
    ["note.result", resultHtml(summary, h)],
    ["note.assessment", note.assessment],
  ];
  const body = (
    <dl className="case-notes-body">
      {rows.map(([label, html]) => (
        <div key={label} className={label === "note.result" ? (summary.passed ? "res ok" : "res bad") : undefined}>
          <dt>
            <Tx k={label} />
          </dt>
          <dd dangerouslySetInnerHTML={{ __html: html }} />
        </div>
      ))}
    </dl>
  );
  if (!collapsible) return <div className="case-notes">{body}</div>;
  return (
    <details className="case-notes" open>
      <summary>
        <Tx k="note.title" />
      </summary>
      {body}
    </details>
  );
}
