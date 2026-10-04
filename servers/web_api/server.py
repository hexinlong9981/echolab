"""手元だけで動く実時間の画面（web/ の「実行」タブ）のための API（M5・ADR-0011）。

    python -m servers.web_api [--port 8765]

- ``127.0.0.1`` にだけつなぐ。公開のサーバとしては使わない（公開するのは静的な回放だけ）。
- ``GET /api/info``：使えるドメイン・台本のデモ・API キーの有無・OCR の有無・コストの上限
- ``POST /api/ask``：1 回質問し、結果と実行トレースの出来事を返す（静的な回放と同じ形）
- それ以外の GET は、ビルド済みの ``web/dist`` のファイルを返す

ほかのサイトのページからこの API を呼ばれない（API キーの費用を使われない）よう、
``Content-Type: application/json`` を必須にし、``Origin`` が自分以外なら拒む。
実物の Claude（``llm: anthropic``）はコアのコストの上限（日次・月次）に従う。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from core.agent.runtime import REPO_ROOT, report_cli_error, startup_errors
from core.gateway.gateway import available_domains
from core.trace import DEFAULT_TRACE_DIR
from servers.vision_mcp import ocr
from servers.web_api.runner import DEMOS, ask

DIST = REPO_ROOT / "web" / "dist"
MAX_BODY = 64 * 1024
MAX_QUESTION = 2000

# 質問は 1 件ずつ実行する（コストの台帳を同時に書かないため）
_ask_lock = threading.Lock()


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


def info() -> dict[str, Any]:
    from core.gateway import Budget

    budget = Budget.from_config(REPO_ROOT)
    return {
        "domains": available_domains(REPO_ROOT),
        "demos": [dict(d) for d in DEMOS],
        "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ocr": ocr.available(),
        "caps_usd": {"daily": str(budget.daily_usd), "monthly": str(budget.monthly_usd)},
    }


def parse_ask(body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/ask`` の本文を検査する。

    台本は DEMOS のものだけを使う（任意のファイルは読ませない）。
    """
    llm = body.get("llm")
    if llm not in ("scripted", "anthropic"):
        raise ApiError(HTTPStatus.BAD_REQUEST, "llm は scripted か anthropic です")
    fake = body.get("fake_backend", False)
    if not isinstance(fake, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, "fake_backend は真偽値です")
    if llm == "scripted":
        demo = next((d for d in DEMOS if d["id"] == body.get("demo")), None)
        if demo is None:
            raise ApiError(
                HTTPStatus.BAD_REQUEST, "台本モードでは demo（デモの ID）を指定してください"
            )
        return {
            "question": demo["question"],
            "domain": demo["domain"],
            "llm_kind": "scripted",
            "script": REPO_ROOT / demo["script"],
            "fake_backend": fake,
            "context": {"progress": demo["progress"]} if "progress" in demo else None,
        }
    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ApiError(HTTPStatus.BAD_REQUEST, "question（質問）がありません")
    if len(question) > MAX_QUESTION:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"質問は {MAX_QUESTION} 文字までです")
    domain = body.get("domain")
    if domain not in available_domains(REPO_ROOT):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"ドメインが見つかりません: {domain}")
    progress = body.get("progress")
    if progress is not None and (not isinstance(progress, str) or not 0 < len(progress) <= 40):
        raise ApiError(HTTPStatus.BAD_REQUEST, "progress は 40 文字までの文字列です（例 novel:5）")
    return {
        "question": question,
        "domain": domain,
        "llm_kind": "anthropic",
        "script": None,
        "fake_backend": fake,
        # 進み具合は利用者が指定する（ドメインが受け付けなければ ContextError で 400）
        "context": {"progress": progress} if progress else None,
    }


def run_ask(params: dict[str, Any]) -> dict[str, Any]:
    with _ask_lock:
        try:
            return asyncio.run(ask(**params, trace_dir=REPO_ROOT / DEFAULT_TRACE_DIR))
        except startup_errors() as e:
            raise ApiError(HTTPStatus.BAD_REQUEST, _startup_message(e)) from e


def _startup_message(e: BaseException) -> str:
    import contextlib
    import io

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        report_cli_error(e)
    return err.getvalue().splitlines()[0].removeprefix("エラー: ") if err.getvalue() else str(e)


class Handler(BaseHTTPRequestHandler):
    server_version = "EchoLabLocal"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[web_api] {format % args}\n")

    # -- API ---------------------------------------------------------------

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/api/info":
            self._json(HTTPStatus.OK, info())
            return
        self._static()

    def do_POST(self) -> None:
        try:
            if self.path != "/api/ask":
                raise ApiError(HTTPStatus.NOT_FOUND, "見つかりません")
            self._check_origin()
            if self.headers.get_content_type() != "application/json":
                raise ApiError(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type は application/json です"
                )
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                raise ApiError(HTTPStatus.BAD_REQUEST, "本文の長さが不正です")
            try:
                body = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as e:
                raise ApiError(HTTPStatus.BAD_REQUEST, "本文が JSON ではありません") from e
            if not isinstance(body, dict):
                raise ApiError(HTTPStatus.BAD_REQUEST, "本文は JSON のオブジェクトです")
            self._json(HTTPStatus.OK, run_ask(parse_ask(body)))
        except ApiError as e:
            self._json(e.status, {"error": str(e)})

    def _check_origin(self) -> None:
        origin = self.headers.get("Origin")
        if origin is None:
            return  # ブラウザ以外（curl など）
        port = self.server.server_address[1]
        allowed = {f"http://{h}:{port}" for h in ("127.0.0.1", "localhost")}
        allowed |= {"http://127.0.0.1:5173", "http://localhost:5173"}  # Vite の開発サーバ
        if origin not in allowed:
            raise ApiError(HTTPStatus.FORBIDDEN, "ほかのサイトからは呼べません")

    # -- 静的ファイル --------------------------------------------------------

    def _static(self) -> None:
        if not DIST.is_dir():
            self._text(
                HTTPStatus.NOT_FOUND,
                "web/dist がありません。"
                "先に (cd web && npm ci && npm run build) を実行してください。",
            )
            return
        rel = self.path.split("?")[0].lstrip("/") or "index.html"
        target = (DIST / rel).resolve()
        if not target.is_relative_to(DIST.resolve()) or not target.is_file():
            target = DIST / "index.html"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: HTTPStatus, doc: Any) -> None:
        data = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _text(self, status: HTTPStatus, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="手元だけで動く Web UI の API（127.0.0.1）")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)
    server = make_server(args.port)
    print(f"http://127.0.0.1:{args.port}/ で開いてください（Ctrl+C で終了）", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
