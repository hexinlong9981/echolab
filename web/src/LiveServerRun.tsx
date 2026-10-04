import { useState } from "react";
import { LiveError, type LiveErrorCode, runOnServer, wake } from "./liveApi";
import { RunPlayer } from "./RunPlayer";
import { Tx } from "./Tx";
import type { RunRecord } from "./types";

type State =
  | { kind: "idle" }
  | { kind: "waking" }
  | { kind: "running" }
  | { kind: "done"; run: RunRecord }
  | { kind: "error"; code: LiveErrorCode };

/** デモのリプレイの下に出す「サーバで実際に実行」（公開のデモサーバ、ADR-0013）。 */
export function LiveServerRun({ base, demo, services }: { base: string; demo: string; services: Record<string, string> }) {
  const [state, setState] = useState<State>({ kind: "idle" });

  const start = async () => {
    setState({ kind: "waking" });
    // 休止中なら起動を待つ（1 分ほどかかることがある）
    if (!(await wake(base))) {
      setState({ kind: "error", code: "offline" });
      return;
    }
    setState({ kind: "running" });
    try {
      setState({ kind: "done", run: await runOnServer(base, demo) });
    } catch (e) {
      setState({ kind: "error", code: e instanceof LiveError ? e.code : "other" });
    }
  };

  const busy = state.kind === "waking" || state.kind === "running";
  return (
    <section className="live-server">
      <div className="live-server-head">
        <button onClick={start} disabled={busy}>
          <Tx k={busy ? "server.running" : "server.button"} />
        </button>
        <Tx k="server.note" />
      </div>
      {state.kind === "waking" && <Tx k="server.waking" as="p" />}
      {state.kind === "error" && (
        <p className="error">
          <Tx k={`server.err.${state.code}`} />
        </p>
      )}
      {state.kind === "done" && (
        <>
          <p className="live-server-label">
            <Tx k="server.label" />
            {state.run.live && <Tx k="server.elapsed" p={{ s: (state.run.live.elapsed_ms / 1000).toFixed(1) }} />}
          </p>
          <RunPlayer run={state.run} services={services} />
        </>
      )}
    </section>
  );
}
