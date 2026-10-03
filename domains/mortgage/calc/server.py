"""住宅ローンの計算を MCP サーバ（stdio）として公開する（ADR-0003・ADR-0009）。

``config/services.yaml`` の ``mortgage-calc`` として、コアのゲートウェイが子プロセスで起動する。
calc-engine（Java）と同じ契約で結果を返す：テキスト内容に ``ToolEnvelope`` の JSON
（``values`` は 10 進数の文字列）。入力の誤りは ``isError`` の結果にする。
stdout は MCP の通信に使うので、ほかの出力はしない。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from domains.mortgage.calc.loan import TOOLS, LoanInputError

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

DESCRIPTIONS = {
    "mortgage.equal_payment": (
        "元利均等返済の毎月の返済額・総返済額・利息の合計（固定金利の計算例）"
    ),
    "mortgage.equal_principal": (
        "元金均等返済の初回・最終回の返済額・総返済額・利息の合計（固定金利の計算例）"
    ),
    "mortgage.prepayment": (
        "元利均等返済の途中で一部を繰上返済したときの効果（期間短縮型・返済額軽減型）。"
        "繰上返済の直前の残高・その後の毎月の返済額と残りの回数・利息の合計と軽減額・短縮した回数"
    ),
}


def wire_name(tool: str) -> str:
    return tool.replace(".", "_")


def tool_definitions() -> list[types.Tool]:
    """公開するツール。入力スキーマは ``schemas/<wire 名>.schema.json``。"""
    return [
        types.Tool(
            name=wire_name(tool),
            description=DESCRIPTIONS[tool],
            inputSchema=json.loads(
                (SCHEMA_DIR / f"{wire_name(tool)}.schema.json").read_text(encoding="utf-8")
            ),
        )
        for tool in TOOLS
    ]


def call(wire: str, arguments: dict[str, Any]) -> types.CallToolResult:
    """1 回の呼び出し。結果は ``ToolEnvelope`` の JSON。

    データを参照しないので、未確認データ（``unverified_inputs``）は常に空。
    """
    tool = next((t for t in TOOLS if wire_name(t) == wire), None)
    if tool is None:
        return _error(f"未知のツールです: {wire}")
    try:
        values = TOOLS[tool](arguments)
    except LoanInputError as e:
        return _error(f"入力が不正です: {e}")
    envelope = {
        "tool": tool,
        "values": {k: format(v, "f") for k, v in values.items()},
        "unverified_inputs": [],
        "data_version": None,
    }
    text = json.dumps(envelope, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)], isError=True
    )


def build_server() -> Server:
    server: Server = Server("mortgage-calc")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tool_definitions()

    # 入力はゲートウェイが同じスキーマで検査済み。ここでは計算の前提（残高・回数など）を検査し、
    # 日本語の説明を返す
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        return call(name, arguments)

    return server


async def main() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
