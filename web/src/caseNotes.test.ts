import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { resultHtml } from "./caseNotes";
import { CASE_NOTES, translate } from "./i18n";
import jaRuby from "./locales/ja.ruby.json";
import type { CaseSummary } from "./types";

const REPO = resolve(import.meta.dirname, "../..");
const SUITES = {
  faithfulness: "evals/faithfulness/cases.yaml",
  redteam: "evals/redteam/cases.yaml",
  mushoku: "evals/faithfulness/mushoku.yaml",
  spoilers: "evals/redteam/spoilers.yaml",
  mortgage: "evals/faithfulness/mortgage.yaml",
};
// 評価のケースの ID（YAML から読む。export.py の SUITES と同じ組み合わせ）
const keys = Object.entries(SUITES).flatMap(([suite, path]) =>
  [...readFileSync(resolve(REPO, path), "utf-8").matchAll(/^ {2}- id: ([a-z0-9-]+)$/gm)].map((m) => `${suite}/${m[1]}`),
);

const stripRuby = (html: string) =>
  html
    .replace(/<rt[^>]*>.*?<\/rt>/g, "")
    .replace(/<rp>.*?<\/rp>/g, "")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");

describe("case notes", () => {
  it("すべての評価ケースに、3 つの言語で内容・用意・評価がある（余分も無い）", () => {
    expect(keys.length).toBeGreaterThanOrEqual(30);
    for (const lang of ["ja", "en", "zh"] as const) {
      expect(Object.keys(CASE_NOTES[lang]).sort(), lang).toEqual([...keys].sort());
      for (const k of keys) {
        const note = CASE_NOTES[lang][k];
        expect(note?.content, `${lang} ${k}`).toBeTruthy();
        expect(note?.purpose, `${lang} ${k}`).toBeTruthy();
        expect(note?.assessment, `${lang} ${k}`).toBeTruthy();
      }
    }
  });

  it("日本語のルビ（ja.ruby.json の caseNotes）が caseNotes.ja.json と一致する", () => {
    const ruby = jaRuby.caseNotes as Record<string, Record<string, string>>;
    for (const [k, note] of Object.entries(CASE_NOTES.ja)) {
      for (const field of ["content", "purpose", "assessment"] as const) {
        expect(stripRuby(ruby[k]?.[field] ?? ""), `${k} ${field}`).toBe(note[field]);
      }
    }
  });

  it("結果の文は実行のデータから作る（合否・状態・差し戻し・拒否・引用）", () => {
    const t = (key: string, params?: Record<string, string | number>) => translate("ja", key, params);
    const base: CaseSummary = {
      id: "x",
      title: "x",
      status: "fallback",
      passed: true,
      faithful: true,
      drafts: 3,
      drafts_rejected: 3,
      tool_errors: 0,
      cited: [],
      failures: [],
      key: "suite-x",
      run_id: "r",
    };
    const ok = resultHtml(base, t);
    expect(ok).toContain("合格");
    expect(ok).toContain("fallback");
    expect(ok).toContain("差し戻し 3 回");
    expect(ok).not.toContain("拒んだ");
    expect(ok).toContain("引用は無し");
    const bad = resultHtml({ ...base, passed: false, tool_errors: 2, cited: ["c1.a", "c2.b"] }, t);
    expect(bad).toContain("不合格");
    expect(bad).toContain("拒んだツール呼び出し 2 件");
    expect(bad).toContain("出典 2 個");
  });
});
