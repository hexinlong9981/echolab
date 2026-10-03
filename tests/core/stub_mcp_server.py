"""試験用の小さな stdio の MCP サーバ。calc-engine と同じ形の結果（ToolEnvelope の JSON）を返す。

Java の jar に依存せずに :class:`core.gateway.McpStdioBackend` を試すために使う。
"""

from __future__ import annotations

import json
import os
from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

server = FastMCP("stub")


@server.tool(name="stub_add", description="a + b（試験用）")
def stub_add(a: float, b: float) -> str:
    total = Decimal(str(a)) + Decimal(str(b))
    return json.dumps(
        {
            "tool": "stub.add",
            "values": {"sum": str(total)},
            "unverified_inputs": ["stub_data:sample"],
            "data_version": os.environ.get("STUB_DATA_VERSION"),
        }
    )


@server.tool(name="stub_fail", description="必ず失敗する（試験用）")
def stub_fail(reason: str) -> str:
    raise ToolError(f"入力が不正です: {reason}")


@server.tool(name="stub_garbage", description="JSON でない結果を返す（試験用）")
def stub_garbage() -> str:
    return "これは JSON ではありません"


@server.tool(name="stub_hidden", description="domain.yaml で宣言しないツール（試験用）")
def stub_hidden() -> str:
    return json.dumps({"tool": "stub.hidden", "values": {"x": "1"}})


if __name__ == "__main__":
    server.run()
