"""``python -m servers.vision_mcp`` で MCP サーバ（stdio）を起動する。"""

import asyncio

from servers.vision_mcp.server import main

asyncio.run(main())
