"""実行トレース（JSONL）の書き込み・読み出しと、Agent が残す出来事の中身。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from core.contracts import CallOutcome, SourceValue
from core.trace import TraceWriter, new_run_id, read_trace, to_jsonable
from tests.core.test_agent import DMG_A, run_agent, tool_turn


def test_writer_appends_one_json_object_per_line(tmp_path: Path) -> None:
    trace = TraceWriter(tmp_path / "t", run_id="run-1")
    trace.emit("question", question="質問")
    trace.emit("answer", answer="回答", cost_usd=Decimal("0.0100"))
    assert trace.path == tmp_path / "t" / "run-1.jsonl"
    lines = trace.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert [r["event"] for r in records] == ["question", "answer"]
    assert all(r["run_id"] == "run-1" and r["ts"].endswith("+00:00") for r in records)
    assert records[1]["cost_usd"] == "0.0100"  # Decimal は丸めずに文字列
    assert "質問" in lines[0]  # 日本語をエスケープしない
    assert read_trace(trace.path, "answer") == [records[1]]


def test_to_jsonable_handles_contract_types() -> None:
    @dataclass(frozen=True)
    class Box:
        values: tuple[Decimal, ...]

    outcome = CallOutcome(
        "c1",
        "damage.expected",
        {"atk": 2000},
        sources=(SourceValue("c1.total", Decimal("6192.000"), "damage.expected", ("x:y",)),),
    )
    doc = to_jsonable({"outcome": outcome, "box": Box((Decimal("1.50"),)), "p": Path("a/b")})
    assert doc["outcome"]["sources"][0] == {
        "source_id": "c1.total",
        "value": "6192.000",
        "tool": "damage.expected",
        "unverified_inputs": ["x:y"],
    }
    assert doc["box"] == {"values": ["1.50"]}
    assert doc["p"] == "a/b"
    json.dumps(doc)


def test_run_ids_are_unique_and_sortable() -> None:
    ids = {new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(len(i.split("-")[0]) == 16 for i in ids)


async def test_agent_trace_records_the_whole_run(tmp_path: Path) -> None:
    result, _, _ = await run_agent(
        tmp_path,
        [
            tool_turn(("damage_expected", DMG_A), usage={"input_tokens": 10, "output_tokens": 5}),
            {"text": "合計は 6192 です。"},
            {"text": "合計は [[c1.total|0]] です。"},
        ],
    )
    assert result.trace_path.parent == tmp_path / "traces"
    assert result.trace_path.name == f"{result.run_id}.jsonl"
    records = read_trace(result.trace_path)
    assert [r["event"] for r in records] == [
        "question",
        "llm_call",
        "tool_call",
        "tool_result",
        "llm_call",
        "verdict",
        "llm_call",
        "verdict",
        "answer",
    ]
    assert {r["run_id"] for r in records} == {result.run_id}

    question = records[0]
    assert question["question"] == "攻撃力 2000 のときの期待ダメージは？"
    assert question["model"] == "claude-opus-5-5" and question["llm"] == "ScriptedLLM"

    call = records[1]
    assert call["usage"]["input_tokens"] == 10
    assert Decimal(call["usd"]) == Decimal("0.00014")
    assert call["tool_uses"][0]["name"] == "damage_expected"

    tool_call, tool_result = records[2], records[3]
    assert tool_call["name"] == "damage_expected" and tool_call["input"] == DMG_A
    assert tool_result["tool_use_id"] == tool_call["tool_use_id"]
    sources = {s["source_id"]: s["value"] for s in tool_result["outcome"]["sources"]}
    assert Decimal(sources["c1.total"]) == Decimal("6192")

    rejected, accepted = records[5], records[7]
    assert (rejected["ok"], rejected["draft"], rejected["template"]) == (
        False,
        1,
        "合計は 6192 です。",
    )
    assert accepted["ok"] is True and accepted["cited"] == ["c1.total"]

    answer = records[-1]
    assert answer["status"] == "answered"
    assert answer["answer"] == "合計は 6,192 です。"
    assert answer["cited"] == ["c1.total"]
    assert answer["drafts_rejected"] == 1
    assert Decimal(answer["cost_usd"]) == Decimal("0.00014")
