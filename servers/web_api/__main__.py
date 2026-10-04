"""``python -m servers.web_api`` で、手元だけで動く Web UI の API を起動する。"""

import sys

from servers.web_api.server import main

sys.exit(main())
