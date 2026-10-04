import { BaseEdge, type EdgeProps, type InternalNode, useInternalNode } from "@xyflow/react";

// 箱の中心どうしを結ぶ直線を、それぞれの箱の枠で切った矢印（React Flow の「floating edge」）。
// 既定の接続点（箱の上下）を使うと、横に並んだ箱の矢印が回り込んで読みにくいため。

function center(node: InternalNode) {
  const { x, y } = node.internals.positionAbsolute;
  const w = node.measured.width ?? 0;
  const h = node.measured.height ?? 0;
  return { x: x + w / 2, y: y + h / 2, w, h };
}

/** 中心 c の箱（幅 w・高さ h）の枠と、c から (tx, ty) へ向かう直線の交点。 */
export function borderPoint(c: { x: number; y: number; w: number; h: number }, tx: number, ty: number) {
  const dx = tx - c.x;
  const dy = ty - c.y;
  if (dx === 0 && dy === 0) return { x: c.x, y: c.y };
  const scale = 1 / Math.max(Math.abs(dx) / (c.w / 2 || 1), Math.abs(dy) / (c.h / 2 || 1));
  return { x: c.x + dx * scale, y: c.y + dy * scale };
}

export function FloatingEdge({ id, source, target, markerEnd, style }: EdgeProps) {
  const s = useInternalNode(source);
  const t = useInternalNode(target);
  if (!s || !t) return null;
  const sc = center(s);
  const tc = center(t);
  const a = borderPoint(sc, tc.x, tc.y);
  const b = borderPoint(tc, sc.x, sc.y);
  return <BaseEdge id={id} path={`M ${a.x},${a.y} L ${b.x},${b.y}`} markerEnd={markerEnd} style={style} />;
}
