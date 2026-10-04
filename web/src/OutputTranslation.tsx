import { outputText, useI18n } from "./i18n";
import { Tx } from "./Tx";

/**
 * プログラムの出力（回答・差し戻しの指摘・エラー）の参考訳。英中のページだけ。
 * 原文（日本語のまま表示する）が本体で、これは「訳（プログラムの出力ではない）」と明示して添える。
 * 台本モードの出力は毎回同じなので訳を用意してある。実物の Claude の回答など、訳の無いものはその旨を出す。
 */
export function OutputTranslation({ texts }: { texts: string[] }) {
  const { lang } = useI18n();
  if (lang === "ja" || texts.length === 0) return null;
  const translated = texts.map((t) => outputText(lang, t));
  if (translated.every((t) => t === null)) return <Tx k="out.none" as="p" />;
  return (
    <div className="translation">
      <Tx k="out.translation" as="p" />
      {translated.map((t, i) => (
        <pre key={i}>{t ?? texts[i]}</pre>
      ))}
    </div>
  );
}
