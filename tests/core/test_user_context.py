"""利用者が指定する項目（domain.yaml の user_context）と、数値でない説明文（texts）の試験。

利用者の値は LLM に見せず、LLM が送っても拒み、ゲートウェイがサービスへの入力に加える（ADR-0012）。
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.agent.__main__ import parse_context
from core.agent.runtime import CliError
from core.contracts import ToolEnvelope, ToolError, ToolSpec
from core.gateway import Budget, ContextError, Gateway

SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "progress": {"type": "string"}},
    "required": ["query", "progress"],
    "additionalProperties": False,
}


class LoreBackend:
    """progress を受け取り、texts と数値を返す偽のサービス。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def list_tools(self) -> list[ToolSpec]:
        return [ToolSpec("lore_search", "設定の検索", SCHEMA)]

    async def call_tool(self, wire_name: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        self.calls.append(dict(arguments))
        if "progress" not in arguments:
            raise ToolError("progress がありません")
        return ToolEnvelope(
            tool="lore.search",
            values={"count": Decimal(1)},
            texts={"roxy_teacher": "ロキシーは家庭教師になる"},
        )

    async def aclose(self) -> None:
        pass


def _repo(tmp_path: Path, user_context: list[str] | None) -> Path:
    pack = tmp_path / "domains/demo"
    pack.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "name": "demo",
        "tools": [{"name": "lore.search", "service": "lore", "description": "検索"}],
    }
    if user_context is not None:
        manifest["user_context"] = user_context
    (pack / "domain.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return tmp_path


async def _open(tmp_path: Path, backend: LoreBackend, **kwargs: Any) -> Gateway:
    budget = Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))
    return await Gateway.open(tmp_path, "demo", backends={"lore": backend}, budget=budget, **kwargs)


async def test_user_context_is_hidden_from_the_llm_and_injected(tmp_path: Path) -> None:
    backend = LoreBackend()
    gw = await _open(_repo(tmp_path, ["progress"]), backend, context={"progress": "novel:5"})
    [spec] = [s for s in gw.tool_specs() if s.name == "lore_search"]
    assert "progress" not in spec.input_schema["properties"]
    assert spec.input_schema["required"] == ["query"]
    assert gw.context == {"progress": "novel:5"}

    outcome = await gw.call("lore_search", {"query": "ロキシー"})
    assert outcome.error is None
    assert backend.calls == [{"query": "ロキシー", "progress": "novel:5"}]
    assert outcome.arguments == {"query": "ロキシー"}  # LLM が送ったものだけを記録する
    assert outcome.for_llm()["texts"] == {"roxy_teacher": "ロキシーは家庭教師になる"}
    assert [s.source_id for s in outcome.sources] == ["c1.count"]  # texts は出典 ID にならない


async def test_llm_cannot_set_or_widen_the_user_context(tmp_path: Path) -> None:
    backend = LoreBackend()
    gw = await _open(_repo(tmp_path, ["progress"]), backend, context={"progress": "novel:5"})
    outcome = await gw.call("lore_search", {"query": "x", "progress": "novel:26"})
    assert outcome.error is not None and "progress" in outcome.error
    assert backend.calls == []  # サービスは呼ばない


async def test_missing_user_context_is_a_tool_error(tmp_path: Path) -> None:
    backend = LoreBackend()
    gw = await _open(_repo(tmp_path, ["progress"]), backend)
    outcome = await gw.call("lore_search", {"query": "x"})
    assert outcome.error is not None and "--context progress=" in outcome.error
    assert backend.calls == []


async def test_undeclared_context_is_rejected_at_open(tmp_path: Path) -> None:
    with pytest.raises(ContextError, match="progress を受け付けません"):
        await _open(_repo(tmp_path, None), LoreBackend(), context={"progress": "novel:5"})


def test_parse_context() -> None:
    assert parse_context(["progress=novel:5", " a = b "]) == {"progress": "novel:5", "a": "b"}
    with pytest.raises(CliError, match="NAME=VALUE"):
        parse_context(["progress"])


def test_envelope_texts_from_json() -> None:
    env = ToolEnvelope.from_json({"tool": "x.y", "values": {}, "texts": {"a": "文"}})
    assert env.texts == {"a": "文"}
    assert ToolEnvelope.from_json({"tool": "x.y", "values": {}}).texts == {}
