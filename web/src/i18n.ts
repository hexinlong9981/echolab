// 画面の文言（日本語・英語・中国語）。言語は URL の ?lang=、保存した選択、ブラウザの言語の順で決める。
// 日本語の文言には、漢字のふりがなとカタカナの元の英単語をルビで付ける（locales/ja.ruby.json。非公開の
// ツールで生成し、出力だけをコミットする）。記録の中身（質問・回答・検証器の指摘・エラー）はプログラムの
// 実際の出力なので、翻訳もルビもしない。
import { createContext, useContext } from "react";
import en from "./locales/en.json";
import ja from "./locales/ja.json";
import jaRuby from "./locales/ja.ruby.json";
import outputsEn from "./locales/outputs.en.json";
import outputsZh from "./locales/outputs.zh.json";
import questionsEn from "./locales/questions.en.json";
import questionsZh from "./locales/questions.zh.json";
import titlesEn from "./locales/titles.en.json";
import titlesZh from "./locales/titles.zh.json";
import zh from "./locales/zh.json";

export type Lang = "ja" | "en" | "zh";
export const LANGS: { code: Lang; label: string; html: string }[] = [
  { code: "ja", label: "日本語", html: "ja" },
  { code: "en", label: "English", html: "en" },
  { code: "zh", label: "中文", html: "zh-CN" },
];

type Dict = Record<string, string>;
export const DICTS: Record<Lang, Dict> = { ja, en, zh };
const RUBY: { ui: Dict; titles: Dict } = jaRuby;
const TITLES: Record<"en" | "zh", Dict> = { en: titlesEn, zh: titlesZh };

const isLang = (x: string | null | undefined): x is Lang => x === "ja" || x === "en" || x === "zh";

/** 保存した設定を読む（プライベートモードなどで使えなければ null）。 */
function load(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function store(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 保存できない環境では無視する
  }
}

export function detectLang(): Lang {
  const fromUrl = new URLSearchParams(window.location.search).get("lang");
  if (isLang(fromUrl)) return fromUrl;
  const saved = load("echolab-lang");
  if (isLang(saved)) return saved;
  const browser = (navigator.language || "ja").toLowerCase();
  if (browser.startsWith("zh")) return "zh";
  if (browser.startsWith("en")) return "en";
  return "ja";
}

/** ルビの表示（日本語のとき）。既定はどちらも表示。 */
export function loadRubyPrefs(): { furi: boolean; eng: boolean } {
  return { furi: load("echolab-furi") !== "off", eng: load("echolab-eng") !== "off" };
}

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ESCAPES[c] ?? c);

type Params = Record<string, string | number>;

function fill(text: string, params: Params, escape: boolean): string {
  return text.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = params[name];
    if (v === undefined) return `{${name}}`;
    return escape ? escapeHtml(String(v)) : String(v);
  });
}

/** 文言（プレーンテキスト。属性・選択肢など HTML にできない所で使う）。無い言語は日本語に落とす。 */
export function translate(lang: Lang, key: string, params: Params = {}): string {
  return fill(DICTS[lang][key] ?? ja[key as keyof typeof ja] ?? key, params, false);
}

/** 文言（HTML）。日本語はルビ付き。差し込む値（記録の中身など）はエスケープし、ルビは付けない。 */
export function translateHtml(lang: Lang, key: string, params: Params = {}): string {
  if (lang === "ja" && RUBY.ui[key]) return fill(RUBY.ui[key], params, true);
  return fill(escapeHtml(DICTS[lang][key] ?? ja[key as keyof typeof ja] ?? key), params, true);
}

const QUESTIONS: Record<"en" | "zh", Dict> = { en: questionsEn, zh: questionsZh };

/** 質問の訳（英中）。質問は日本語の原文をキーにする。日本語のとき・訳が無いときは null。 */
export function questionText(lang: Lang, jaQuestion: string): string | null {
  return lang === "ja" ? null : (QUESTIONS[lang][jaQuestion] ?? null);
}

const OUTPUTS: Record<"en" | "zh", Dict> = { en: outputsEn, zh: outputsZh };

/** プログラムの出力（回答・差し戻しの指摘・エラー）の参考訳。原文をキーにする。無ければ null。 */
export function outputText(lang: Lang, jaText: string): string | null {
  return lang === "ja" ? null : (OUTPUTS[lang][jaText] ?? null);
}

/** データの表示名（プレーンテキスト。select の選択肢など）。 */
export function titleText(lang: Lang, key: string, jaTitle: string): string {
  return lang === "ja" ? jaTitle : (TITLES[lang][key] ?? jaTitle);
}

/** データの表示名（デモ・評価・ケース）。日本語はデータの title にルビを付け、英中はここの訳を使う。 */
export function titleHtml(lang: Lang, key: string, jaTitle: string): string {
  if (lang === "ja") return RUBY.titles[jaTitle] ?? escapeHtml(jaTitle);
  return escapeHtml(TITLES[lang][key] ?? jaTitle);
}

export type T = (key: string, params?: Params) => string;

export interface I18n {
  lang: Lang;
  /** プレーンテキスト */
  t: T;
  /** HTML（日本語はルビ付き） */
  h: T;
}

export const makeI18n = (lang: Lang): I18n => ({
  lang,
  t: (key, params) => translate(lang, key, params),
  h: (key, params) => translateHtml(lang, key, params),
});

export const LangContext = createContext<I18n>(makeI18n("ja"));

export const useI18n = () => useContext(LangContext);
