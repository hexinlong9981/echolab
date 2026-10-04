// 評価ケースの「結果」の文：実行のデータ（状態・下書き・差し戻し・拒否・引用・合否）から作る。手で書かない。
import type { T } from "./i18n";
import type { CaseSummary } from "./types";

export function resultHtml(c: CaseSummary, h: T): string {
  const parts = [
    h(c.passed ? "note.r.pass" : "note.r.fail"),
    h("note.r.status", { status: c.status }),
    h("note.r.drafts", { drafts: c.drafts, rejected: c.drafts_rejected }),
  ];
  if (c.tool_errors > 0) parts.push(h("note.r.refused", { n: c.tool_errors }));
  parts.push(c.cited.length > 0 ? h("note.r.cited", { n: c.cited.length }) : h("note.r.noCite"));
  return parts.join(" ");
}
