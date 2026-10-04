"""``python -m domains.mushoku.service`` で MCP サーバ（stdio）を起動する。"""

import asyncio

from domains.mushoku.service.server import main

asyncio.run(main())
