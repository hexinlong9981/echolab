import { Background, type Edge, MarkerType, type Node, ReactFlow } from "@xyflow/react";
import { useMemo } from "react";
import { FloatingEdge } from "./FloatingEdge";
import { useI18n } from "./i18n";
import type { NodeId, Step } from "./replay";

// 箱の配置は固定（左から右へ：質問 → Agent → ゲートウェイ → サービス、下に検証器 → 回答）。
const LAYOUT: Record<NodeId, { x: number; y: number; label: string }> = {
  user: { x: 0, y: 120, label: "node.user" },
  agent: { x: 170, y: 120, label: "node.agent" },
  llm: { x: 170, y: 0, label: "node.llm" },
  budget: { x: 0, y: 0, label: "node.budget" },
  gateway: { x: 370, y: 120, label: "node.gateway" },
  "calc-engine": { x: 600, y: 0, label: "node.calc" },
  "mortgage-calc": { x: 600, y: 80, label: "node.mortgage" },
  "vision-mcp": { x: 600, y: 160, label: "node.vision" },
  "mushoku-lore": { x: 600, y: 240, label: "node.mushoku" },
  compare: { x: 600, y: 320, label: "node.compare" },
  verifier: { x: 170, y: 250, label: "node.verifier" },
  answer: { x: 0, y: 250, label: "node.answer" },
};

// 箱の組（向きは問わない）。往復する組も線は 1 本で、そのコマで通った向きに矢印を付ける
const LINKS: [NodeId, NodeId][] = [
  ["user", "agent"],
  ["agent", "llm"],
  ["agent", "budget"],
  ["agent", "gateway"],
  ["gateway", "calc-engine"],
  ["gateway", "mortgage-calc"],
  ["gateway", "vision-mcp"],
  ["gateway", "mushoku-lore"],
  ["gateway", "compare"],
  ["agent", "verifier"],
  ["verifier", "answer"],
];

const EDGE_TYPES = { floating: FloatingEdge };

export function FlowDiagram({ step }: { step: Step | undefined }) {
  const { h, t } = useI18n();
  const nodes: Node[] = useMemo(
    () =>
      (Object.keys(LAYOUT) as NodeId[]).map((id) => ({
        id,
        position: { x: LAYOUT[id].x, y: LAYOUT[id].y },
        // 改行（\n）を <br> にした、ルビ付きの見出し
        data: { label: <span dangerouslySetInnerHTML={{ __html: h(LAYOUT[id].label).replaceAll("\n", "<br>") }} /> },
        className: `flow-node ${step?.nodes[id] ?? ""}`,
        draggable: false,
        selectable: false,
      })),
    [step, h],
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
    <div className="flow" aria-label={t("diagram.aria")}>
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
