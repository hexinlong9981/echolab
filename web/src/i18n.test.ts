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
  const suites = { faithfulness: "evals/faithfulness/cases.yaml", mortgage: "evals/faithfulness/mortgage.yaml", redteam: "evals/redteam/cases.yaml" };
  const cases = Object.entries(suites).flatMap(([suite, path]) =>
    [...readFileSync(resolve(REPO, path), "utf-8").matchAll(/^ {2}- id: ([a-z0-9-]+)$/gm)].map((m) => `${suite}/${m[1]}`),
  );
  const keys = [...demos, ...Object.keys(suites).map((s) => `suite/${s}`), ...cases];

  it("ID を読み取れている", () => {
    expect(demos.length).toBe(3);
    expect(cases.length).toBeGreaterThanOrEqual(20);
  });

  it("英語と中国語の表示名がそろっている（余分も無い）", () => {
    expect(Object.keys(titlesEn).sort()).toEqual([...keys].sort());
    expect(Object.keys(titlesZh).sort()).toEqual([...keys].sort());
  });
});
