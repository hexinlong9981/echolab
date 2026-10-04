import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DICTS, titleHtml, translate, translateHtml } from "./i18n";
import jaRuby from "./locales/ja.ruby.json";
import titlesEn from "./locales/titles.en.json";
import titlesZh from "./locales/titles.zh.json";

const REPO = resolve(import.meta.dirname, "../..");

/** ルビの印を外したプレーンテキスト（<rt>・<rp> の中身を捨て、タグを外す）。 */
const stripRuby = (html: string) =>
  html
    .replace(/<rt[^>]*>.*?<\/rt>/g, "")
    .replace(/<rp>.*?<\/rp>/g, "")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");

describe("locales", () => {
  it("すべての文言が日本語・英語・中国語にある", () => {
    const keys = Object.keys(DICTS.ja).sort();
    expect(Object.keys(DICTS.en).sort()).toEqual(keys);
    expect(Object.keys(DICTS.zh).sort()).toEqual(keys);
  });

  it("日本語のルビ（ja.ruby.json）が ja.json と一致する（古いままなら生成し直す）", () => {
    for (const [key, text] of Object.entries(DICTS.ja)) {
      if (!text) continue;
      expect(jaRuby.ui[key as keyof typeof jaRuby.ui], key).toBeDefined();
      expect(stripRuby(jaRuby.ui[key as keyof typeof jaRuby.ui]), key).toBe(text);
    }
    for (const [title, html] of Object.entries(jaRuby.titles)) {
      expect(stripRuby(html)).toBe(title);
    }
  });

  it("差し込む値（記録の中身）はエスケープし、ルビも付けない", () => {
    const evil = '<img src=x onerror="alert(1)">質問';
    for (const lang of ["ja", "en", "zh"] as const) {
      const html = translateHtml(lang, "s.question.d", { question: evil, domain: "wuwa", n: 1 });
      expect(html).not.toContain("<img");
      expect(html).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;質問");
    }
    expect(translate("en", "raw", { text: "そのまま" })).toBe("そのまま");
  });

  it("日本語の画面はルビ付き、英中はプレーン", () => {
    expect(translateHtml("ja", "tab.evals")).toContain('<ruby class="furi">');
    expect(translateHtml("en", "tab.evals")).toBe("Evals");
    expect(titleHtml("zh", "suite/redteam", "注入（プロンプトインジェクション）")).toBe("提示词注入");
  });
});

describe("titles", () => {
  // データの表示名の ID：デモ（servers/web_api/runner.py）・評価（export.py）・ケース（evals の YAML）
  const runner = readFileSync(resolve(REPO, "servers/web_api/runner.py"), "utf-8");
  const demos = [...runner.matchAll(/"id": "(demo-[a-z-]+)"/g)].map((m) => `demo/${m[1]}`);
  const suites = {
    faithfulness: "evals/faithfulness/cases.yaml",
    mortgage: "evals/faithfulness/mortgage.yaml",
    redteam: "evals/redteam/cases.yaml",
    mushoku: "evals/faithfulness/mushoku.yaml",
    spoilers: "evals/redteam/spoilers.yaml",
  };
  const cases = Object.entries(suites).flatMap(([suite, path]) =>
    [...readFileSync(resolve(REPO, path), "utf-8").matchAll(/^ {2}- id: ([a-z0-9-]+)$/gm)].map((m) => `${suite}/${m[1]}`),
  );
  const keys = [...demos, ...Object.keys(suites).map((s) => `suite/${s}`), ...cases];

  it("ID を読み取れている", () => {
    expect(demos.length).toBe(4);
    expect(cases.length).toBeGreaterThanOrEqual(20);
  });

  it("英語と中国語の表示名がそろっている（余分も無い）", () => {
    expect(Object.keys(titlesEn).sort()).toEqual([...keys].sort());
    expect(Object.keys(titlesZh).sort()).toEqual([...keys].sort());
  });
});

import questionsEn from "./locales/questions.en.json";
import questionsJa from "./locales/questions.ja.json";
import questionsZh from "./locales/questions.zh.json";
import { questionText } from "./i18n";

describe("questions", () => {
  // questions.ja.json はデモと評価ケースの質問の一覧（tests/test_web_api.py が YAML と一致を確かめる）
  it("すべての質問に英語と中国語の訳がある", () => {
    const en: Record<string, string> = questionsEn;
    const zh: Record<string, string> = questionsZh;
    for (const q of questionsJa) {
      expect(en[q], q).toBeTruthy();
      expect(zh[q], q).toBeTruthy();
    }
    expect(Object.keys(en).sort()).toEqual([...questionsJa].sort());
    expect(Object.keys(zh).sort()).toEqual([...questionsJa].sort());
  });

  it("訳でも原文の数値とファイルのパスがそのまま入っている", () => {
    const tokens = (s: string) => s.match(/[0-9]+(?:\.[0-9]+)?|[\w/.-]+\.png|\/etc\/passwd/g) ?? [];
    for (const q of questionsJa) {
      for (const lang of ["en", "zh"] as const) {
        const translated = tokens(questionText(lang, q) ?? "");
        for (const t of tokens(q)) expect(translated, `${lang}: ${q}`).toContain(t);
      }
    }
  });

  it("日本語のページと訳の無い質問は null", () => {
    expect(questionText("ja", questionsJa[0] as string)).toBeNull();
    expect(questionText("en", "未知の質問")).toBeNull();
  });
});

import { existsSync, readdirSync } from "node:fs";
import outputsEn from "./locales/outputs.en.json";
import outputsZh from "./locales/outputs.zh.json";

describe("program outputs", () => {
  // CI は python -m servers.web_api.export の後に npm test を実行する（web.yml）。手元でデータが無ければ飛ばす
  const runsDir = resolve(__dirname, "../public/data/runs");
  const texts = new Set<string>();
  if (existsSync(runsDir)) {
    for (const f of readdirSync(runsDir)) {
      const run = JSON.parse(readFileSync(resolve(runsDir, f), "utf-8")) as { events: Record<string, unknown>[] };
      for (const e of run.events) {
        if (e.event === "answer") texts.add(e.answer as string);
        if (e.event === "verdict") for (const p of e.problems as string[]) texts.add(p);
        if (e.event === "tool_result") {
          const error = (e.outcome as { error: string | null }).error;
          if (error) texts.add(error);
        }
        if (e.event === "llm_error") texts.add(e.error as string);
        if (e.event === "budget_exceeded") texts.add(e.reason as string);
      }
    }
  }

  it.skipIf(texts.size === 0)("書き出したデータの回答・指摘・エラーにすべて英語と中国語の訳がある", () => {
    const en: Record<string, string> = outputsEn;
    const zh: Record<string, string> = outputsZh;
    for (const t of texts) {
      expect(en[t], t).toBeTruthy();
      expect(zh[t], t).toBeTruthy();
    }
  });

  it("訳でも原文の数値・出典 ID・パスがそのまま入っている", () => {
    const tokens = (s: string) => s.match(/c[0-9]+\.[a-z_]+|[0-9][0-9,]*(?:\.[0-9]+)?%?|[\w/.-]+\.png|ECHOLAB_\w+/g) ?? [];
    for (const [ja, en] of Object.entries(outputsEn as Record<string, string>)) {
      const zh = (outputsZh as Record<string, string>)[ja] ?? "";
      for (const t of tokens(ja)) {
        expect(tokens(en), `en: ${ja}`).toContain(t);
        expect(tokens(zh), `zh: ${ja}`).toContain(t);
      }
    }
  });
});
