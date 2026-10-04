import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 相対パスで出力する（Cloudflare Pages でも、手元の API サーバ（web/dist を配る）でも同じ成果物を使う）。
// 開発サーバでは /api を手元の API（python -m servers.web_api）へ中継する。
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  test: { environment: "node" },
});
