import type { DataIndex } from "./types";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

export function EvalsView({ index, onOpen }: { index: DataIndex; onOpen: (runId: string) => void }) {
  return (
    <main className="evals pad">
      <p className="muted">
        評価は台本モード（API キー不要）で CI が毎回実行します。台本には「LLM が数値を書いてしまった」「指示に従ってしまった」場合の応答もわざと入れてあり、
        それでも検証器・ゲートウェイが止めることを確かめます。実物の Claude での評価は手元で手動で行います（まだ実施していません）。
      </p>
      <div className="cards">
        {index.suites.map((s) => (
          <section key={s.id} className={`card ${s.ok ? "" : "bad"}`}>
            <h2>{s.title}</h2>
            <dl>
              <dt>数値の忠実度</dt>
              <dd className={s.faithfulness === 1 ? "ok" : "bad"}>{s.faithfulness.toFixed(3)}</dd>
              <dt>合格したケース</dt>
              <dd>
                {s.passed} / {s.total}
              </dd>
              <dt>差し戻し率</dt>
              <dd>{pct(s.draft_rejection_rate)}</dd>
              <dt>拒んだツール呼び出し</dt>
              <dd>{s.tool_errors}</dd>
            </dl>
          </section>
        ))}
      </div>
      {index.suites.map((s) => (
        <section key={s.id}>
          <h2>
            {s.title}（ドメイン {s.domain}）
          </h2>
          <table className="cases">
            <thead>
              <tr>
                <th>ケース</th>
                <th>状態</th>
                <th>下書き</th>
                <th>差し戻し</th>
                <th>拒否</th>
                <th>合否</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {s.cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <code>{c.id}</code>
                    <div className="muted">{c.title}</div>
                  </td>
                  <td>{c.status}</td>
                  <td className="num">{c.drafts}</td>
                  <td className="num">{c.drafts_rejected}</td>
                  <td className="num">{c.tool_errors}</td>
                  <td className={c.passed ? "ok" : "bad"}>{c.passed ? "合格" : `不合格：${c.failures.join("；")}`}</td>
                  <td>{c.run_id && <button onClick={() => onOpen(c.run_id as string)}>回放 ▶</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </main>
  );
}
