"""``python -m domains.mortgage.calc`` で MCP サーバ（stdio）を起動する。"""

import asyncio

from domains.mortgage.calc.server import main

asyncio.run(main())
