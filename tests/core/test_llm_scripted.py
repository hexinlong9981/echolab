"""台本の LLM（ScriptedLLM）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.agent.llm import ScriptedLLM, ScriptExhausted, ScriptMismatch

ROOT = Path(__file__).resolve().parents[2]


async def test_plays_turns_in_order_and_records_calls() -> None:
    llm = ScriptedLLM(
        [
            {"tool_uses": [{"name": "damage_expected", "input": {"atk": 1}}], "text": "計算"},
            {"text": "完了", "usage": {"input_tokens": 7, "output_tokens": None}},
        ]
    )
    first = await llm.complete(system="s", messages=[{"role": "user", "content": "q"}], tools=[])
    assert first.stop_reason == "tool_use"
    assert first.tool_uses[0].id == "toolu_scripted_01"
    assert first.raw_content == [
        {"type": "text", "text": "計算"},
        {
            "type": "tool_use",
            "id": "toolu_scripted_01",
            "name": "damage_expected",
            "input": {"atk": 1},
        },
    ]
    second = await llm.complete(system="s", messages=[], tools=[])
    assert (second.stop_reason, second.text) == ("end_turn", "完了")
    assert second.usage == {
        "input_tokens": 7,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    assert llm.remaining == 0
    assert llm.calls[0]["messages"] == [{"role": "user", "content": "q"}]
    with pytest.raises(ScriptExhausted):
        await llm.complete(system="s", messages=[], tools=[])


async def test_expect_checks_previous_message() -> None:
    llm = ScriptedLLM([{"text": "a", "expect": "差し戻し"}])
    with pytest.raises(ScriptMismatch):
        await llm.complete(system="s", messages=[{"role": "user", "content": "別の文"}], tools=[])


def test_loads_example_script() -> None:
    llm = ScriptedLLM.from_file(ROOT / "core/agent/examples/compare_builds.yaml")
    assert llm.remaining == 4
