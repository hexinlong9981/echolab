"""stdio の MCP サーバ（例 calc-engine）への接続（ADR-0008）。

公式の ``mcp`` SDK のクライアントを使う。サーバのプロセスと MCP のセッションは、
専用のタスクの中で :class:`contextlib.AsyncExitStack` に積んで管理する。
``mcp`` の stdio クライアントは anyio のキャンセルスコープを使い、開いたタスクと
同じタスクで閉じる必要があるため、呼び出し側のタスクがどこで閉じても安全なようにしている。
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

from core.contracts import ToolEnvelope, ToolError, ToolSpec

SERVICES_PATH = Path("config/services.yaml")

#: 1 回のツール呼び出しの応答を待つ上限（秒）。超えたら ToolError にして、質問全体を止めない。
DEFAULT_CALL_TIMEOUT_SECONDS = 30.0


class ServiceStartError(RuntimeError):
    """ツールサービスを起動できない（実行ファイル・jar が無い、起動直後に終了したなど）。

    メッセージには原因と直し方を書く（CLI はそのまま利用者に見せる）。
    """


def load_services(repo_root: Path) -> dict[str, dict[str, Any]]:
    """``config/services.yaml`` のサービス名 → 設定。"""
    doc = yaml.safe_load((repo_root / SERVICES_PATH).read_text(encoding="utf-8"))
    return dict(doc["services"])


def resolve_executable(name: str, env: Mapping[str, str]) -> str:
    """起動する実行ファイルを決める。

    ``java`` が PATH に無くても ``JAVA_HOME`` が設定されていれば、その ``bin/java`` を使う
    （対話シェル以外では ``~/.bashrc`` の PATH 設定が効かないことがあるため）。
    """
    if name == "java" and shutil.which("java", path=env.get("PATH")) is None:
        java_home = env.get("JAVA_HOME")
        if java_home and (Path(java_home) / "bin" / "java").exists():
            return str(Path(java_home) / "bin" / "java")
    return name


def check_command(
    command: Sequence[str], *, cwd: Path, env: Mapping[str, str], service: str
) -> None:
    """起動する前に、実行ファイルと ``-jar`` の jar があることを確かめる。

    :raises ServiceStartError: 見つからないとき（直し方をメッセージに含める）。
    """
    executable = resolve_executable(command[0], env)
    if shutil.which(executable, path=env.get("PATH")) is None:
        hint = ""
        if command[0] == "java":
            hint = (
                "JDK 21 を入れて PATH に java を通すか、環境変数 JAVA_HOME を"
                "（$JAVA_HOME/bin/java があるように）設定してください。"
            )
        raise ServiceStartError(
            f"サービス {service} の実行ファイル {command[0]} が見つかりません。{hint}"
        )
    for flag, value in itertools.pairwise(command[1:]):
        if flag != "-jar":
            continue
        jar = Path(value)
        if not jar.is_absolute():
            jar = cwd / jar
        if not jar.is_file():
            raise ServiceStartError(
                f"サービス {service} の jar がありません: {jar}。{_build_hint(Path(value))}"
            )


def _build_hint(jar: Path) -> str:
    """jar の作り方の案内。Gradle の既定の出力先（``<プロジェクト>/build/libs``）なら手順を示す。"""
    if jar.parent.name == "libs" and jar.parent.parent.name == "build":
        project = jar.parent.parent.parent
        return f"先に jar を作ってください：(cd {project} && ./gradlew bootJar)"
    return "先に jar を作ってください。"


class McpStdioBackend:
    """stdio の MCP サーバを子プロセスとして起動し、ツールを呼ぶ（``ToolBackend`` の実装）。"""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        call_timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS,
    ) -> None:
        """
        :param command: 起動するコマンド（``[実行ファイル, 引数...]``）。
        :param cwd: 子プロセスの作業ディレクトリ。
        :param env: ``os.environ`` に重ねる環境変数。
        :param call_timeout: 1 回のツール呼び出しの応答を待つ上限（秒）。
        """
        if not command:
            raise ValueError("起動するコマンドが空です")
        self.command = list(command)
        self.cwd = Path(cwd)
        self.env = dict(env or {})
        self._session: ClientSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.call_timeout = call_timeout
        # 同じサーバへの呼び出しは 1 本ずつ送る。MCP Java SDK の stdio サーバは、起動直後に
        # 並行して応答を書き出すと「Failed to enqueue message」で応答を失うことがあるため
        # （計算は数ミリ秒なので、直列にしても待ち時間はほぼ変わらない）。
        self._call_lock = asyncio.Lock()

    @classmethod
    async def for_service(cls, repo_root: Path, service: str) -> McpStdioBackend:
        """``config/services.yaml`` の設定でサービスを起動する。

        作業ディレクトリはリポジトリ直下。
        """
        services = load_services(repo_root)
        if service not in services:
            raise ValueError(f"config/services.yaml に無いサービスです: {service}")
        config = services[service]
        if config.get("transport", "stdio") != "stdio":
            raise ValueError(f"stdio 以外の接続方式には対応していません: {service}")
        # 設定の env は既定値：同じ名前の環境変数がプロセスにあれば、そちらを優先する
        env = {k: str(v) for k, v in (config.get("env") or {}).items() if k not in os.environ}
        command = [str(c) for c in config["command"]]
        check_command(command, cwd=repo_root, env={**os.environ, **env}, service=service)
        backend = cls(command, cwd=repo_root, env=env)
        try:
            await backend.start()
        except Exception as e:
            raise ServiceStartError(
                f"サービス {service} を起動できませんでした（{type(e).__name__}: {e}）。"
                f"起動コマンド: {' '.join(command)}"
            ) from e
        return backend

    async def start(self) -> None:
        """サーバを起動し、MCP の初期化が終わるまで待つ。"""
        if self._task is not None:
            raise RuntimeError("すでに起動しています")
        ready: asyncio.Future[ClientSession] = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run(ready))
        try:
            self._session = await ready
        except BaseException:
            await self.aclose()
            raise

    async def _run(self, ready: asyncio.Future[ClientSession]) -> None:
        params = StdioServerParameters(
            command=resolve_executable(self.command[0], {**os.environ, **self.env}),
            args=self.command[1:],
            env={**os.environ, **self.env},
            cwd=self.cwd,
        )
        try:
            async with contextlib.AsyncExitStack() as stack:
                read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                ready.set_result(session)
                await self._stop.wait()
        except BaseException as e:
            if not ready.done():
                ready.set_exception(e)
                return
            raise

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP サーバに接続していません（start() を先に呼んでください）")
        return self._session

    async def list_tools(self) -> list[ToolSpec]:
        session = self._require_session()
        specs: list[ToolSpec] = []
        cursor: str | None = None
        while True:
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            result = await session.list_tools(params=params)
            specs.extend(
                ToolSpec(name=t.name, description=t.description or "", input_schema=t.inputSchema)
                for t in result.tools
            )
            cursor = result.nextCursor
            if not cursor:
                return specs

    async def call_tool(self, wire_name: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        session = self._require_session()
        async with self._call_lock:
            try:
                result = await session.call_tool(
                    wire_name,
                    dict(arguments),
                    read_timeout_seconds=timedelta(seconds=self.call_timeout),
                )
            except McpError as e:
                # 応答待ちの時間切れや、サーバが返した JSON-RPC のエラー
                raise ToolError(f"ツール {wire_name} の呼び出しに失敗しました: {e}") from e
        text = "".join(c.text for c in result.content if isinstance(c, types.TextContent))
        if result.isError:
            raise ToolError(text or f"ツール {wire_name} が失敗しました")
        try:
            return ToolEnvelope.from_json(json.loads(text))
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError) as e:
            raise ToolError(f"ツール {wire_name} の結果を解釈できません: {e}") from e

    async def aclose(self) -> None:
        """セッションを閉じ、サーバのプロセスを終了させる。何度呼んでもよい。"""
        self._session = None
        task, self._task = self._task, None
        if task is None:
            return
        self._stop.set()
        with contextlib.suppress(Exception):
            await task

    async def __aenter__(self) -> McpStdioBackend:
        if self._task is None:
            await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
