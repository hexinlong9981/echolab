"""スクリーンショットの読み取りを MCP サーバ（stdio）として公開する（ADR-0010）。

``config/services.yaml`` の ``vision-mcp`` として、コアのゲートウェイが子プロセスで起動する。
テンプレート（``domains/*/vision/*.yaml``）ごとに 1 つのツールを公開する。どのツールを使えるかは、
各ドメインの ``domain.yaml`` の宣言でゲートウェイが決める（既定拒否）。

結果は calc-engine と同じ ``ToolEnvelope`` の JSON で、``values`` は数値だけ。
画像の中の文字列（説明文や、書き込まれた指示）は結果に入らない。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from servers.vision_mcp import ocr
from servers.vision_mcp.reader import (
    ReadError,
    Template,
    extract,
    load_templates,
    resolve_image,
    template_dirs,
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "読み取るスクリーンショット。作業ディレクトリからの相対パスか絶対パス",
    "properties": {
        "image": {
            "type": "string",
            "minLength": 1,
            "maxLength": 1000,
            "description": (
                "画像（PNG・JPEG）のパス。"
                "読める場所は ECHOLAB_VISION_ROOTS（既定は作業ディレクトリ）"
            ),
        }
    },
    "required": ["image"],
    "additionalProperties": False,
}


def wire_name(tool: str) -> str:
    return tool.replace(".", "_")


def tool_definitions(templates: dict[str, Template]) -> list[types.Tool]:
    return [
        types.Tool(name=wire_name(t.tool), description=t.description, inputSchema=INPUT_SCHEMA)
        for t in templates.values()
    ]


def call(
    templates: dict[str, Template], wire: str, arguments: dict[str, Any], *, cwd: Path
) -> types.CallToolResult:
    template = next((t for t in templates.values() if wire_name(t.tool) == wire), None)
    if template is None:
        return _error(f"未知のツールです: {wire}")
    image_text = arguments.get("image")
    if not isinstance(image_text, str) or not image_text:
        return _error("入力が不正です: image（画像のパス）がありません")
    try:
        image = resolve_image(image_text, cwd=cwd)
        values = extract(template, ocr.read_lines(image))
    except (ReadError, ocr.OcrError) as e:
        return _error(str(e))
    envelope = {
        "tool": template.tool,
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


def build_server(cwd: Path | None = None) -> Server:
    cwd = cwd or Path.cwd()
    templates = load_templates(template_dirs(cwd))
    server: Server = Server("vision-mcp")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tool_definitions(templates)

    # 入力はゲートウェイが同じスキーマで検査済み。ここではパス・画像・読み取りの誤りを日本語で返す
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        # OCR は子プロセスで数百ミリ秒かかるので、イベントループを止めない
        return await asyncio.to_thread(call, templates, name, arguments, cwd=cwd)

    return server


async def main() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
