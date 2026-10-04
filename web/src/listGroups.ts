// 左のリストの分組（デモ・評価ごと）。開いておく分組を決める純粋な関数（listGroups.test.ts）。
import type { DataIndex } from "./types";

export const DEMOS_GROUP = "demos";

/** 実行の鍵（key）を含む分組。見つからなければデモの分組。 */
export function groupOf(index: Pick<DataIndex, "demos" | "suites">, key: string | null): string {
  if (key) {
    if (index.demos.some((d) => d.key === key)) return DEMOS_GROUP;
    const suite = index.suites.find((s) => s.cases.some((c) => c.key === key));
    if (suite) return suite.id;
  }
  return DEMOS_GROUP;
}
