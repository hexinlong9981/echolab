import { questionText, useI18n } from "./i18n";
import { Tx } from "./Tx";

/** 質問（プログラムへの入力なので日本語の原文が本体）。英中のページでは訳を出し、その下に原文を小さく添える。 */
export function Question({ text }: { text: string }) {
  const { lang } = useI18n();
  const translated = questionText(lang, text);
  if (!translated) return <p className="question">Q. {text}</p>;
  return (
    <div className="question">
      <p>Q. {translated}</p>
      <p className="original" lang="ja">
        <Tx k="q.original" />: {text}
      </p>
    </div>
  );
}
