import { describe, expect, it } from "vitest";
import { DEMOS_GROUP, groupOf } from "./listGroups";
import type { DataIndex } from "./types";

const index = {
  demos: [{ key: "demo-a" }],
  suites: [
    { id: "faithfulness", cases: [{ key: "faithfulness-x" }, { key: null }] },
    { id: "redteam", cases: [{ key: "redteam-y" }] },
  ],
} as unknown as Pick<DataIndex, "demos" | "suites">;

describe("groupOf", () => {
  it("選んだ実行を含む分組を開く", () => {
    expect(groupOf(index, "demo-a")).toBe(DEMOS_GROUP);
    expect(groupOf(index, "faithfulness-x")).toBe("faithfulness");
    expect(groupOf(index, "redteam-y")).toBe("redteam");
  });

  it("選んでいない・見つからないときはデモの分組", () => {
    expect(groupOf(index, null)).toBe(DEMOS_GROUP);
    expect(groupOf(index, "nope")).toBe(DEMOS_GROUP);
  });
});
