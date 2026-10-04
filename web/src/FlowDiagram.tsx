import { Background, type Edge, MarkerType, type Node, ReactFlow } from "@xyflow/react";
import { useMemo } from "react";
import { FloatingEdge } from "./FloatingEdge";
import type { NodeId, Step } from "./replay";

// 箱の配置は固定（左から右へ：質問 → Agent → ゲートウェイ → サービス、下に検証器 → 回答）。
const LAYOUT: Record<NodeId, { x: number; y: number; label: string }> = {
  user: { x: 0, y: 120, label: "質問" },
  agent: { x: 170, y: 120, label: "Agent" },
  llm: { x: 170, y: 0, label: "LLM（Claude）" },
  gateway: { x: 370, y: 120, label: "ゲートウェイ\n許可リスト・形式" },
  "calc-engine": { x: 600, y: 0, label: "calc-engine\n（Java）" },
  "mortgage-calc": { x: 600, y: 80, label: "mortgage-calc\n（Python）" },
  "vision-mcp": { x: 600, y: 160, label: "vision-mcp\n（OCR）" },
  compare: { x: 600, y: 240, label: "比較ツール\ncompare.*" },
  verifier: { x: 170, y: 250, label: "検証器・レンダラ" },
  answer: { x: 0, y: 250, label: "出典付きの回答" },
};

// 箱の組（向きは問わない）。往復する組も線は 1 本で、そのコマで通った向きに矢印を付ける
const LINKS: [NodeId, NodeId][] = [
  ["user", "agent"],
  ["agent", "llm"],
  ["agent", "gateway"],
  ["gateway", "calc-engine"],
  ["gateway", "mortgage-calc"],
  ["gateway", "vision-mcp"],
  ["gateway", "compare"],
  ["agent", "verifier"],
  ["verifier", "answer"],
];

const EDGE_TYPES = { floating: FloatingEdge };

export function FlowDiagram({ step }: { step: Step | undefined }) {
  const nodes: Node[] = useMemo(
    () =>
      (Object.keys(LAYOUT) as NodeId[]).map((id) => ({
        id,
        position: { x: LAYOUT[id].x, y: LAYOUT[id].y },
        data: { label: LAYOUT[id].label },
        className: `flow-node ${step?.nodes[id] ?? ""}`,
        draggable: false,
        selectable: false,
      })),
    [step],
  );
  const edges: Edge[] = useMemo(() => {
    const lit = new Set(step?.edges ?? []);
    return LINKS.map(([a, b]) => {
      const forward = lit.has(`${a}>${b}`);
      const backward = lit.has(`${b}>${a}`);
      const on = forward || backward;
      return {
        id: `${a}-${b}`,
        type: "floating",
        // 逆向きだけ通ったコマは、矢印が逆を向くよう端を入れ替える
        source: backward && !forward ? b : a,
        target: backward && !forward ? a : b,
        animated: on,
        className: on ? "lit" : "",
        markerEnd: on ? { type: MarkerType.ArrowClosed } : undefined,
      };
    });
  }, [step]);
  return (
    <div className="flow" aria-label="処理の流れの図">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        edgeTypes={EDGE_TYPES}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnDrag={false}
        proOptions={{ hideAttribution: false }}
      >
        <Background gap={24} />
      </ReactFlow>
    </div>
  );
}
