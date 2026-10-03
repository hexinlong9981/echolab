"""McpStdioBackend を、Python で書いた stdio の MCP サーバ（stub_mcp_server.py）で試す。"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.contracts import ToolError
from core.gateway import Budget, Gateway, McpStdioBackend, ServiceStartError, UnknownDomainError

STUB = Path(__file__).with_name("stub_mcp_server.py")
ROOT = Path(__file__).resolve().parents[2]


async def test_backend_lists_and_calls_tools(tmp_path: Path) -> None:
    backend = McpStdioBackend(
        [sys.executable, str(STUB)], cwd=tmp_path, env={"STUB_DATA_VERSION": "v9"}
    )
    async with backend:
        names = {t.name for t in await backend.list_tools()}
        assert names == {"stub_add", "stub_fail", "stub_garbage", "stub_hidden"}
        spec = next(t for t in await backend.list_tools() if t.name == "stub_add")
        assert spec.description == "a + b（試験用）"
        assert set(spec.input_schema["properties"]) == {"a", "b"}

        envelope = await backend.call_tool("stub_add", {"a": 1.5, "b": 2.25})
        assert envelope.tool == "stub.add"
        assert envelope.values == {"sum": Decimal("3.75")}
        assert envelope.unverified_inputs == ("stub_data:sample",)
        # env は os.environ に重ねて子プロセスに渡る
        assert envelope.data_version == "v9"

        with pytest.raises(ToolError, match="入力が不正です: だめ"):
            await backend.call_tool("stub_fail", {"reason": "だめ"})
        with pytest.raises(ToolError, match="解釈できません"):
            await backend.call_tool("stub_garbage", {})
    # 閉じた後は呼べない。aclose は何度呼んでもよい
    with pytest.raises(RuntimeError):
        await backend.list_tools()
    await backend.aclose()


async def test_backend_start_failure_is_reported(tmp_path: Path) -> None:
    backend = McpStdioBackend(["/nonexistent/echolab-no-such-command"], cwd=tmp_path)
    with pytest.raises(Exception):  # noqa: B017 起動の失敗は種類を問わず伝わればよい
        await backend.start()
    await backend.aclose()


def _write_repo(root: Path, command: list[str] | None = None) -> None:
    (root / "config").mkdir(exist_ok=True)
    (root / "config/services.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "services": {
                    "stub": {
                        "transport": "stdio",
                        "command": command or [sys.executable, str(STUB)],
                        "env": {"STUB_DATA_VERSION": "v1"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "domains/demo").mkdir(parents=True, exist_ok=True)
    (root / "domains/demo/domain.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "demo",
                "tools": [
                    {"name": "stub.add", "service": "stub", "description": "足し算"},
                    {"name": "stub.fail", "service": "stub", "description": "失敗"},
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


async def test_gateway_starts_services_from_config(tmp_path: Path) -> None:
    """backends を渡さなければ、config/services.yaml に従って MCP サーバを起動する。"""
    _write_repo(tmp_path)
    budget = Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))
    async with await Gateway.open(tmp_path, "demo", budget=budget) as gw:
        names = [s.name for s in gw.tool_specs()]
        assert names == ["stub_add", "stub_fail", "compare_diff", "compare_ratio"]

        ok = await gw.call("stub_add", {"a": 1, "b": 2})
        assert ok.error is None
        assert ok.call_id == "c1"
        assert [(s.source_id, s.value) for s in ok.sources] == [("c1.sum", Decimal(3))]

        assert (await gw.call("stub_add", {"a": "x", "b": 2})).error.startswith("入力が不正")
        assert "だめ" in (await gw.call("stub_fail", {"reason": "だめ"})).error
        hidden = await gw.call("stub_hidden", {})
        assert hidden.error is not None
        assert "許可されていません" in hidden.error


async def test_gateway_from_repo_root_config_unknown_service(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    doc = yaml.safe_load((tmp_path / "domains/demo/domain.yaml").read_text(encoding="utf-8"))
    doc["tools"][0]["service"] = "missing"
    (tmp_path / "domains/demo/domain.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        await Gateway.open(tmp_path, "demo", budget=Budget.from_config(ROOT))


@pytest.mark.parametrize(("shell", "expected"), [(None, "v1"), ("v-shell", "v-shell")])
async def test_config_env_is_a_default_that_the_environment_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shell: str | None, expected: str
) -> None:
    """config/services.yaml の env は既定値。シェルの環境変数があればそちらを使う。"""
    _write_repo(tmp_path)
    if shell is None:
        monkeypatch.delenv("STUB_DATA_VERSION", raising=False)
    else:
        monkeypatch.setenv("STUB_DATA_VERSION", shell)
    async with await McpStdioBackend.for_service(tmp_path, "stub") as backend:
        envelope = await backend.call_tool("stub_add", {"a": 1, "b": 2})
    assert envelope.data_version == expected


async def test_missing_jar_is_reported_before_starting(tmp_path: Path) -> None:
    _write_repo(tmp_path, [sys.executable, "-jar", "svc/build/libs/svc.jar"])
    with pytest.raises(ServiceStartError) as info:
        await McpStdioBackend.for_service(tmp_path, "stub")
    message = str(info.value)
    assert str(tmp_path / "svc/build/libs/svc.jar") in message
    assert "(cd svc && ./gradlew bootJar)" in message


async def test_python_command_uses_the_current_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``python`` は PATH ではなく、コアと同じインタプリタ（同じ依存）で起動する。"""
    _write_repo(tmp_path, ["python", str(STUB)])
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))  # PATH に python が無くてもよい
    async with await McpStdioBackend.for_service(tmp_path, "stub") as backend:
        assert "stub_add" in [s.name for s in await backend.list_tools()]


def test_resolve_executable_python_is_sys_executable() -> None:
    from core.gateway.mcp_backend import resolve_executable

    assert resolve_executable("python", {"PATH": ""}) == sys.executable
    assert resolve_executable("python3", {"PATH": ""}) == "python3"  # 置き換えるのは python だけ


async def test_missing_executable_is_reported(tmp_path: Path) -> None:
    _write_repo(tmp_path, ["echolab-no-such-command", "serve"])
    with pytest.raises(ServiceStartError, match="echolab-no-such-command が見つかりません"):
        await McpStdioBackend.for_service(tmp_path, "stub")


async def test_missing_java_mentions_java_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_repo(tmp_path, ["java", "-jar", "x.jar"])
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("JAVA_HOME", raising=False)
    with pytest.raises(ServiceStartError, match="JAVA_HOME"):
        await McpStdioBackend.for_service(tmp_path, "stub")


async def test_server_that_exits_at_start_is_reported(tmp_path: Path) -> None:
    _write_repo(tmp_path, [sys.executable, "-c", "import sys; sys.exit(1)"])
    with pytest.raises(ServiceStartError, match="サービス stub を起動できませんでした"):
        await McpStdioBackend.for_service(tmp_path, "stub")


async def test_unknown_domain_lists_available_domains(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    budget = Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))
    with pytest.raises(UnknownDomainError, match="使えるドメイン: demo"):
        await Gateway.open(tmp_path, "nope", budget=budget)
