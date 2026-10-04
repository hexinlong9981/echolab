"""公開のデモサーバ（M7・ADR-0013）。決まったデモを、実物の計算サービスで実行して返す。

    python -m servers.web_api --public [--host 0.0.0.0] [--port 8080]

Google Cloud Run（無料枠の範囲）で動かす前提。ポートは環境変数 PORT（Cloud Run が渡す）。
費用をゼロに保つため、次のように制限する（Cloud Run の側でも同時実行 1・インスタンス最大 1）。

- LLM は台本だけ（``llm: scripted``）。実物の Claude（``anthropic``）は常に拒む。
  API キーは置かない。
- 実行できるのは決まったデモ（``DEMOS``）だけ。計算サービスは実物（calc-engine の jar・OCR・
  住宅ローン・無職転生）を使い、試験用の偽物には切り替えられない。
- 同時に実行するのは 1 件。待ちは ``QUEUE_MAX`` 件まで（超えたら 503）。1 件の時間の上限は
  ``RUN_TIMEOUT_SECONDS``。
- 接続元（IP）ごとに 1 分 ``PER_MINUTE`` 回・1 日 ``PER_DAY`` 回まで（超えたら 429）。
- 公開のリプレイのサイト（Cloudflare）から呼べるよう、許可した ``Origin`` にだけ CORS を返す。
  許可していない ``Origin`` からの POST は 403（手元の API と同じ考え方）。
- 応答には手元の絶対パスを含めない（``runner.sanitize``）。
  トレースは実行ごとの一時ディレクトリに置く。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from core.agent.runtime import REPO_ROOT, startup_errors
from servers.vision_mcp import ocr
from servers.web_api.runner import DEMOS, ask

MAX_BODY = 4 * 1024
RUN_TIMEOUT_SECONDS = 120.0
QUEUE_MAX = 3
PER_MINUTE = 6
PER_DAY = 60

#: 既定で CORS を許可する Origin（公開の回放のサイトと、Vite の開発サーバ）。
#: 環境変数 ``ECHOLAB_PUBLIC_ORIGINS``（カンマ区切り）で置き換えられる。
DEFAULT_ORIGINS = (
    "https://echolab-web.echolab-web.workers.dev",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


class PublicError(Exception):
    """利用者に返す誤り。``code`` は画面が文言を選ぶための短い名前。"""

    def __init__(
        self, status: HTTPStatus, code: str, message: str, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after


def allowed_origins() -> frozenset[str]:
    configured = os.environ.get("ECHOLAB_PUBLIC_ORIGINS")
    if configured:
        return frozenset(o.strip().rstrip("/") for o in configured.split(",") if o.strip())
    return frozenset(DEFAULT_ORIGINS)


def client_ip(forwarded: str, peer: str) -> str:
    """接続元の IP。前段のプロキシが付けた ``X-Forwarded-For`` の末尾、無ければ直接の相手。"""
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    return parts[-1] if parts else peer


class RateLimiter:
    """接続元ごとの回数の上限（1 分と 1 日の窓）。時刻は差し替えられる（試験用）。"""

    def __init__(
        self,
        per_minute: int = PER_MINUTE,
        per_day: int = PER_DAY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """1 回分を数える。上限を超えていれば ``PublicError``（429）。"""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 86400:
                hits.popleft()
            last_minute = sum(1 for t in hits if now - t < 60)
            if last_minute >= self.per_minute:
                raise PublicError(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    "rate_limited",
                    f"実行は 1 分に {self.per_minute} 回までです。少し待ってから試してください",
                    retry_after=60,
                )
            if len(hits) >= self.per_day:
                raise PublicError(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    "rate_limited",
                    f"実行は 1 日に {self.per_day} 回までです",
                    retry_after=3600,
                )
            hits.append(now)


class Runner:
    """同時に 1 件だけ実行し、待ちの数を制限する。"""

    def __init__(
        self,
        run: Callable[..., dict[str, Any]],
        queue_max: int = QUEUE_MAX,
    ) -> None:
        self._run = run
        self._queue_max = queue_max
        self._lock = threading.Lock()
        self._waiting = 0
        self._count_lock = threading.Lock()

    def __call__(
        self,
        params: dict[str, Any],
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        with self._count_lock:
            if self._waiting > self._queue_max:
                raise PublicError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "busy",
                    "ほかの実行で混み合っています。少し待ってから試してください",
                    retry_after=30,
                )
            self._waiting += 1
        try:
            with self._lock:
                if on_event is not None:
                    try:
                        return self._run(params, on_event=on_event)
                    except TypeError:
                        return self._run(params)
                return self._run(params)
        finally:
            with self._count_lock:
                self._waiting -= 1


def parse_public_ask(body: dict[str, Any]) -> dict[str, Any]:
    """公開の ``POST /api/ask`` の本文を検査する。固定デモ（台本）または即時対話（Gemini）。"""
    stream = bool(body.get("stream"))
    if body.get("fake_backend"):
        raise PublicError(
            HTTPStatus.BAD_REQUEST,
            "fake_not_allowed",
            "公開のサーバは実物の計算サービスだけを使います",
        )
    llm = body.get("llm")
    if llm == "anthropic":
        msg = (
            "公開のサーバでは Claude API は使えません"
            "（Vertex AI Gemini または台本をお使いください）"
        )
        raise PublicError(HTTPStatus.FORBIDDEN, "llm_not_allowed", msg)
    if "demo" in body:
        demo = next((d for d in DEMOS if d["id"] == body.get("demo")), None)
        if demo is None:
            raise PublicError(HTTPStatus.BAD_REQUEST, "unknown_demo", "demo（デモの ID）が不正です")
        return {
            "question": demo["question"],
            "domain": demo["domain"],
            "llm_kind": "scripted",
            "script": REPO_ROOT / demo["script"],
            "fake_backend": False,
            "context": {"progress": demo["progress"]} if "progress" in demo else None,
            "stream": stream,
        }
    question = body.get("question")
    if question is None:
        raise PublicError(
            HTTPStatus.BAD_REQUEST, "unknown_demo", "demo または question を指定してください"
        )
    if not isinstance(question, str) or not question.strip():
        msg = "question（質問文）を指定してください"
        raise PublicError(HTTPStatus.BAD_REQUEST, "missing_question", msg)
    if len(question) > 2000:
        raise PublicError(HTTPStatus.BAD_REQUEST, "question_too_long", "質問は 2000 文字までです")

    from core.gateway.gateway import available_domains

    domain = body.get("domain", "wuwa")
    if domain not in available_domains(REPO_ROOT):
        msg = f"ドメインが見つかりません: {domain}"
        raise PublicError(HTTPStatus.BAD_REQUEST, "unknown_domain", msg)

    progress = body.get("progress")
    if progress is not None and (not isinstance(progress, str) or not 0 < len(progress) <= 40):
        msg = "progress は 40 文字までの文字列です"
        raise PublicError(HTTPStatus.BAD_REQUEST, "invalid_progress", msg)

    return {
        "question": question,
        "domain": domain,
        "llm_kind": "gemini",
        "script": None,
        "fake_backend": False,
        "context": {"progress": progress} if progress else None,
        "stream": stream,
    }


def run_demo(
    params: dict[str, Any],
    timeout: float = RUN_TIMEOUT_SECONDS,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """1 件を実行する。トレースは一時ディレクトリに置き、実行が終わったら消す。"""
    call_params = dict(params)
    call_params.pop("stream", None)
    event_sink = on_event or call_params.pop("on_event", None)

    async def go(trace_dir: Path) -> dict[str, Any]:
        return await asyncio.wait_for(
            ask(**call_params, trace_dir=trace_dir, on_event=event_sink), timeout
        )

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="echolab-public-") as tmp:
        try:
            record = asyncio.run(go(Path(tmp)))
        except TimeoutError as e:
            raise PublicError(
                HTTPStatus.GATEWAY_TIMEOUT,
                "timeout",
                f"実行が {int(timeout)} 秒以内に終わりませんでした",
            ) from e
        except startup_errors() as e:
            raise PublicError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "service_unavailable",
                "計算サービスを起動できませんでした",
            ) from e
    record["live"] = {"elapsed_ms": int((time.monotonic() - started) * 1000)}
    return record


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "public",
        "llm": "scripted",
        "llms": ["scripted", "gemini"],
        "demos": [d["id"] for d in DEMOS],
        "domains": ["wuwa", "mushoku", "mortgage"],
        "ocr": ocr.available(),
        "limits": {"per_minute": PER_MINUTE, "per_day": PER_DAY, "concurrency": 1},
    }


INDEX_TEXT = (
    "EchoLab の公開デモサーバ（台本の LLM・実物の計算サービス）。"
    "画面は https://echolab-web.echolab-web.workers.dev/ から使います。"
    'API：GET /api/health、POST /api/ask {"demo": "<デモの ID>"}\n'
)


def make_handler(
    limiter: RateLimiter, runner: Runner, origins: frozenset[str]
) -> type[BaseHTTPRequestHandler]:
    class PublicHandler(BaseHTTPRequestHandler):
        server_version = "EchoLabPublic"

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(f"[web_api public] {format % args}\n")

        def client_key(self) -> str:
            # Cloud Run の前段（Google Front End）は、X-Forwarded-For の末尾に本当の接続元を
            # 付け足す。先頭の側は利用者が自由に書けるので、末尾を使う（偽の値で回数の上限を
            # すり抜けられないように）
            return client_ip(self.headers.get("X-Forwarded-For", ""), self.client_address[0])

        def origin_ok(self) -> str | None:
            origin = (self.headers.get("Origin") or "").rstrip("/")
            return origin if origin in origins else None

        def do_OPTIONS(self) -> None:
            if self.path.split("?")[0] not in ("/api/ask", "/api/health"):
                self._send(HTTPStatus.NOT_FOUND, b"", "text/plain")
                return
            if self.origin_ok() is None:
                self._send(HTTPStatus.FORBIDDEN, b"", "text/plain")
                return
            self._send(HTTPStatus.NO_CONTENT, b"", None)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/api/health":
                self._json(HTTPStatus.OK, health())
            elif path == "/":
                self._send(HTTPStatus.OK, INDEX_TEXT.encode("utf-8"), "text/plain; charset=utf-8")
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "見つかりません", "code": "not_found"})

        def do_POST(self) -> None:
            try:
                if self.path.split("?")[0] != "/api/ask":
                    raise PublicError(HTTPStatus.NOT_FOUND, "not_found", "見つかりません")
                if self.headers.get("Origin") is not None and self.origin_ok() is None:
                    raise PublicError(
                        HTTPStatus.FORBIDDEN, "forbidden_origin", "このサイトからは呼べません"
                    )
                if self.headers.get_content_type() != "application/json":
                    raise PublicError(
                        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                        "bad_request",
                        "Content-Type は application/json です",
                    )
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    raise PublicError(HTTPStatus.BAD_REQUEST, "bad_request", "本文の長さが不正です")
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError as e:
                    raise PublicError(
                        HTTPStatus.BAD_REQUEST, "bad_request", "本文が JSON ではありません"
                    ) from e
                if not isinstance(body, dict):
                    raise PublicError(
                        HTTPStatus.BAD_REQUEST, "bad_request", "本文は JSON のオブジェクトです"
                    )
                params = parse_public_ask(body)
                limiter.check(self.client_key())
                if params.get("stream"):
                    self._sse(params, runner)
                else:
                    self._json(HTTPStatus.OK, runner(params))
            except PublicError as e:
                self._json(e.status, {"error": str(e), "code": e.code}, e.retry_after)

        # -- 応答 ----------------------------------------------------------

        def _sse(self, params: dict[str, Any], runner: Runner) -> None:
            self.close_connection = True
            self.send_response(HTTPStatus.OK)
            origin = self.origin_ok()
            if origin is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
                self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("X-Robots-Tag", "noindex")
            self.end_headers()

            def on_event(event: dict[str, Any]) -> None:
                chunk = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
                self.wfile.write(chunk)
                self.wfile.flush()

            try:
                runner(params, on_event=on_event)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as e:
                err_doc = {"event": "error", "error": str(e)}
                chunk = f"data: {json.dumps(err_doc, ensure_ascii=False)}\n\n".encode()
                self.wfile.write(chunk)
                self.wfile.flush()

        def _json(self, status: HTTPStatus, doc: Any, retry_after: int | None = None) -> None:
            data = json.dumps(doc, ensure_ascii=False).encode("utf-8")
            self._send(status, data, "application/json; charset=utf-8", retry_after)

        def _send(
            self,
            status: HTTPStatus,
            data: bytes,
            content_type: str | None,
            retry_after: int | None = None,
        ) -> None:
            self.send_response(status)
            origin = self.origin_ok()
            if origin is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
                self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Robots-Tag", "noindex")
            if retry_after is not None:
                self.send_header("Retry-After", str(retry_after))
            if content_type is not None:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

    return PublicHandler


def make_public_server(
    host: str,
    port: int,
    *,
    limiter: RateLimiter | None = None,
    runner: Runner | None = None,
    origins: frozenset[str] | None = None,
) -> ThreadingHTTPServer:
    handler = make_handler(
        limiter or RateLimiter(),
        runner or Runner(run_demo),
        origins if origins is not None else allowed_origins(),
    )
    return ThreadingHTTPServer((host, port), handler)
