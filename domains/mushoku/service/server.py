"""無職転生のパックを MCP サーバ（stdio）として公開する（ADR-0012）。

``config/services.yaml`` の ``mushoku-lore`` として、コアのゲートウェイが子プロセスで起動する。
結果は calc-engine と同じ ``ToolEnvelope`` の JSON（数値は ``values``、事実の文は ``texts``）。
入力の ``progress`` は利用者の進み具合で、ゲートウェイが加える（LLM には見せない）。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from domains.mushoku.service.lore import TOOLS, LoreInputError

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
DATA_VERSION = "draft-1"

DESCRIPTIONS = {
    "lore.search": (
        "設定の短い事実をキーワードで探す（すべてのキーワードを含むもの）。人物・場所の名前でも当たる。"
        "利用者の進み具合より先の事実は返さない。事実の文は texts、件数と出典の巻・話は values"
    ),
    "timeline.age": "出来事の年の、その人物の年齢（出来事の年 − 生年）",
    "timeline.span": "2 つの出来事の間の年数",
    "map.route": "自作の地図で、2 つの場所の間の最短の旅程（日数の合計・区間の数）。道順は texts",
}


def wire_name(tool: str) -> str:
    return tool.replace(".", "_")


def tool_definitions() -> list[types.Tool]:
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
    tool = next((t for t in TOOLS if wire_name(t) == wire), None)
    if tool is None:
        return _error(f"未知のツールです: {wire}")
    try:
        result = TOOLS[tool](arguments)
    except LoreInputError as e:
        return _error(str(e))
    envelope = {
        "tool": tool,
        "values": {k: format(v, "f") for k, v in result.values.items()},
        "texts": result.texts,
        # 資料はすべて未確認の下書き（ADR-0006）
        "unverified_inputs": list(result.unverified),
        "data_version": DATA_VERSION,
    }
    text = json.dumps(envelope, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)], isError=True
    )


def build_server() -> Server:
    server: Server = Server("mushoku-lore")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tool_definitions()

    # 入力はゲートウェイが検査済み（progress はゲートウェイが加えたもの）。ここでは中身を検査する
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
