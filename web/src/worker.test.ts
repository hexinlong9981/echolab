import { describe, expect, it } from "vitest";
import { passwordFrom, safeEqual } from "./worker";

describe("worker Basic Auth", () => {
  it("safeEqual matches identical strings in constant time", () => {
    expect(safeEqual("secret123", "secret123")).toBe(true);
    expect(safeEqual("secret123", "secret124")).toBe(false);
    expect(safeEqual("secret123", "secret")).toBe(false);
    expect(safeEqual("", "")).toBe(true);
  });

  it("passwordFrom parses Basic Auth header properly", () => {
    // btoa("user:my-pass") === "dXNlcjpteS1wYXNz"
    const header = "Basic dXNlcjpteS1wYXNz";
    expect(passwordFrom(header)).toBe("my-pass");

    expect(passwordFrom(null)).toBeNull();
    expect(passwordFrom("Bearer token")).toBeNull();
    expect(passwordFrom("Basic invalid-base64!!")).toBeNull();
  });
});
