import { titleHtml, useI18n } from "./i18n";

/** 文言を HTML で表示する（日本語はふりがな・英語のルビ付き）。 */
export function Tx({
  k,
  p,
  as: Tag = "span",
  className,
}: {
  k: string;
  p?: Record<string, string | number>;
  as?: "span" | "p" | "h2" | "h3" | "div";
  className?: string;
}) {
  const { h } = useI18n();
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: h(k, p) }} />;
}

/** デモ・評価・ケースの表示名。 */
export function Title({ k, ja }: { k: string; ja: string }) {
  const { lang } = useI18n();
  return <span dangerouslySetInnerHTML={{ __html: titleHtml(lang, k, ja) }} />;
}
