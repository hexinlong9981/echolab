"""Agent の往復を、台本の LLM と偽の計算サービスで試す（API キー・Java 不要）。"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from core.agent import FALLBACK_ANSWER, Agent, load_system_prompt
from core.agent.llm import LLMError, ScriptedLLM, ScriptExhausted
from core.contracts import UNVERIFIED_NOTE
from core.gateway import Budget, Gateway
from core.trace import read_trace
from tests.core.fakes import FakeCalcBackend

ROOT = Path(__file__).resolve().parents[2]

DMG_A = {
    "atk": 2000,
    "skill_multiplier": 2.5,
    "dmg_bonus": 0.3,
    "crit_rate": 0.6,
    "crit_dmg": 2.2,
    "defense_constant": 1600,
    "enemy_def": 1000,
    "def_ignore": 0,
    "enemy_res": 0.1,
    "res_shred": 0,
}
DMG_B = {
    **DMG_A,
    "atk": 1800,
    "skill_multiplier": 3.0,
    "dmg_bonus": 0.2,
    "crit_rate": 0.5,
    "crit_dmg": 2.5,
    "enemy_def": 1200,
    "res_shred": 0.3,
}
GACHA = {
    "rules": {
        "base_rate": 0.1,
        "soft_pity_start": 5,
        "soft_pity_increment": 0.1,
        "hard_pity": 10,
        "featured_rate": 0.5,
        "guarantee_after_loss": True,
    },
    "start_pity": 8,
    "guaranteed": True,
    "pulls": 1,
}
QUESTION = "攻撃力 2000 のときの期待ダメージは？"


def make_budget(tmp_path: Path, daily: str = "1", monthly: str = "10") -> Budget:
    return Budget(tmp_path / "costs.jsonl", Decimal(daily), Decimal(monthly))


async def run_agent(
    tmp_path: Path,
    turns: list[dict[str, Any]],
    question: str = QUESTION,
    *,
    backend: FakeCalcBackend | None = None,
    budget: Budget | None = None,
    llm: Any | None = None,
    **agent_kwargs: Any,
):
    """台本で 1 回質問し、(結果, LLM, 偽のサービス) を返す。"""
    backend = backend or FakeCalcBackend()
    llm = llm or ScriptedLLM(turns)
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": backend},
        budget=budget or make_budget(tmp_path),
    ) as gw:
        agent = Agent(
            gateway=gw,
            llm=llm,
            system_prompt=load_system_prompt(ROOT, "wuwa"),
            trace_dir=tmp_path / "traces",
            domain="wuwa",
            **agent_kwargs,
        )
        result = await agent.ask(question)
    return result, llm, backend


def tool_turn(*calls: tuple[str, dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"tool_uses": [{"name": n, "input": i} for n, i in calls], **extra}


async def test_happy_path_renders_cited_values(tmp_path: Path) -> None:
    result, llm, backend = await run_agent(
        tmp_path,
        [
            tool_turn(("damage_expected", DMG_A)),
            {"text": "期待ダメージは [[c1.total|0]]（基礎 [[c1.base|0]]）です。"},
        ],
    )
    assert result.status == "answered"
    assert result.answer == "期待ダメージは 6,192（基礎 5,000）です。"
    assert [s.source_id for s in result.cited] == ["c1.total", "c1.base"]
    assert result.cited[0].value == Decimal("6192.0")
    assert (result.drafts, result.drafts_rejected, result.llm_calls) == (1, 0, 2)
    assert backend.calls == [("damage_expected", DMG_A)]
    assert llm.remaining == 0

    # システムプロンプトはコアの規則 + ドメインのプロンプト。ツールはドメイン + 比較ツール
    first = llm.calls[0]
    assert "回答の規則" in first["system"] and "鳴潮" in first["system"]
    names = [t.name for t in first["tools"]]
    assert names == sorted(names)
    assert {"damage_expected", "echo_score", "compare_diff", "compare_ratio"} <= set(names)

    # 履歴：質問 → 応答（そのまま）→ ツール結果
    msgs = llm.calls[1]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"][0]["type"] == "tool_use"
    [block] = msgs[2]["content"]
    assert block["type"] == "tool_result" and "is_error" not in block
    payload = json.loads(block["content"])
    assert payload["call_id"] == "c1" and payload["values"]["c1.total"].startswith("6192")


async def test_parallel_tool_calls_return_results_in_one_message(tmp_path: Path) -> None:
    result, llm, backend = await run_agent(
        tmp_path,
        [
            tool_turn(("damage_expected", DMG_A), ("damage_expected", DMG_B)),
            tool_turn(
                ("compare_diff", {"a": "c2.total", "b": "c1.total"}),
                ("compare_ratio", {"a": "c2.total", "b": "c1.total"}),
            ),
            {"text": "B は A より [[c3.diff|0]]（[[c4.change|%1]]）高いです。"},
        ],
    )
    assert result.status == "answered"
    assert result.answer == "B は A より 936（15.1%）高いです。"
    assert len(backend.calls) == 2

    msgs = llm.calls[1]["messages"]
    assert len(msgs) == 3  # 2 つの結果が 1 つの利用者メッセージにまとまる
    uses = [b for b in msgs[1]["content"] if b["type"] == "tool_use"]
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == [u["id"] for u in uses]
    assert [json.loads(r["content"])["call_id"] for r in results] == ["c1", "c2"]
    # 2 回目の往復も同じ
    assert len(llm.calls[2]["messages"][-1]["content"]) == 2


async def test_tool_error_is_returned_and_agent_recovers(tmp_path: Path) -> None:
    bad = {k: v for k, v in GACHA.items() if k != "rules"}
    result, llm, _ = await run_agent(
        tmp_path,
        [
            tool_turn(("gacha_probability_within", bad)),
            tool_turn(("gacha_probability_within", GACHA), expect="is_error"),
            {"text": "確率は [[c2.probability|%0]] です。"},
        ],
    )
    assert result.status == "answered"
    assert result.answer == "確率は 60% です。"
    [err] = llm.calls[1]["messages"][-1]["content"]
    assert err["is_error"] is True
    assert "error" in json.loads(err["content"])
    assert result.tool_calls == 2


async def test_unknown_tool_is_an_error_result_not_an_exception(tmp_path: Path) -> None:
    result, _, backend = await run_agent(
        tmp_path,
        [
            tool_turn(("gacha_simulate_everything", {})),
            {"text": "そのツールは使えませんでした。", "expect": "is_error"},
        ],
    )
    assert result.status == "answered"
    assert backend.calls == []


async def test_rejected_draft_is_retried_with_feedback(tmp_path: Path) -> None:
    result, llm, _ = await run_agent(
        tmp_path,
        [
            tool_turn(("damage_expected", DMG_A)),
            {"text": "期待ダメージは 6192 です。"},
            {"text": "期待ダメージは [[c1.total|0]] です。", "expect": "差し戻し"},
        ],
    )
    assert result.status == "answered"
    assert result.answer == "期待ダメージは 6,192 です。"
    assert (result.drafts, result.drafts_rejected) == (2, 1)
    feedback = llm.calls[2]["messages"][-1]
    assert feedback["role"] == "user" and "6192" in feedback["content"]

    verdicts = read_trace(result.trace_path, "verdict")
    assert [v["ok"] for v in verdicts] == [False, True]
    assert verdicts[0]["problems"]


async def test_falls_back_without_numbers_after_retries(tmp_path: Path) -> None:
    bad = {"text": "期待ダメージは 6192 です。"}
    result, llm, _ = await run_agent(
        tmp_path,
        [tool_turn(("damage_expected", DMG_A)), bad, bad, bad],
    )
    assert result.status == "fallback"
    assert result.answer == FALLBACK_ANSWER
    assert not re.search(r"\d", result.answer)
    assert (result.drafts, result.drafts_rejected) == (3, 3)
    assert result.cited == ()
    assert llm.remaining == 0  # 初回 + 書き直し 2 回で止まる


async def test_answer_note_is_appended_to_verified_answers_only(tmp_path: Path) -> None:
    note = "※ 計算例であり、助言ではありません。"
    result, _, _ = await run_agent(
        tmp_path,
        [tool_turn(("damage_expected", DMG_A)), {"text": "期待ダメージは [[c1.total|0]] です。"}],
        answer_note=note,
    )
    assert result.status == "answered"
    assert result.answer == f"期待ダメージは 6,192 です。\n\n{note}"

    bad = {"text": "答えは 7 です。"}
    fallback, _, _ = await run_agent(tmp_path, [bad], max_retries=0, answer_note=note)
    assert fallback.status == "fallback"
    assert note not in fallback.answer


def test_load_answer_note_reads_the_manifest(tmp_path: Path) -> None:
    from core.agent import load_answer_note

    assert load_answer_note(ROOT, "wuwa") is None
    pack = tmp_path / "domains/demo"
    pack.mkdir(parents=True)
    (pack / "domain.yaml").write_text(
        "name: demo\nanswer_note: '  注記です。 '\n", encoding="utf-8"
    )
    assert load_answer_note(tmp_path, "demo") == "注記です。"


async def test_max_retries_is_configurable(tmp_path: Path) -> None:
    bad = {"text": "答えは 7 です。"}
    result, _, _ = await run_agent(tmp_path, [bad], max_retries=0)
    assert result.status == "fallback"
    assert result.drafts_rejected == 1


async def test_unverified_inputs_add_note(tmp_path: Path) -> None:
    backend = FakeCalcBackend(unverified={"gacha.probability_within": ("gacha_rules:x",)})
    result, _, _ = await run_agent(
        tmp_path,
        [
            tool_turn(("gacha_probability_within", GACHA)),
            {"text": "確率は [[c1.probability|%0]] です。"},
        ],
        backend=backend,
    )
    assert result.status == "answered"
    assert result.answer.endswith(UNVERIFIED_NOTE)
    assert result.cited[0].unverified_inputs == ("gacha_rules:x",)


async def test_budget_exceeded_before_any_llm_call(tmp_path: Path) -> None:
    llm = ScriptedLLM([])  # 呼ばれたら ScriptExhausted
    result, _, _ = await run_agent(tmp_path, [], budget=make_budget(tmp_path, daily="0"), llm=llm)
    assert result.status == "budget_exceeded"
    assert "日次の上限" in result.answer
    assert "ECHOLAB_DAILY_USD" in result.answer and "config/budget.yaml" in result.answer
    assert result.llm_calls == 0 and llm.calls == []
    events = [e["event"] for e in read_trace(result.trace_path)]
    assert events == ["question", "budget_exceeded", "answer"]


async def test_budget_exceeded_mid_run_and_cost_is_recorded(tmp_path: Path) -> None:
    budget = make_budget(tmp_path, daily="0.01")
    usage = {"input_tokens": 1000, "output_tokens": 500}  # 0.004 + 0.01 = 0.014 USD
    result, llm, _ = await run_agent(
        tmp_path,
        [tool_turn(("damage_expected", DMG_A), usage=usage), {"text": "未使用"}],
        budget=budget,
    )
    assert result.status == "budget_exceeded"
    assert "（使用額 0.014 USD / 上限 0.01 USD）" in result.answer
    assert result.cost_usd == Decimal("0.014")
    assert budget.spent_today() == Decimal("0.014")
    assert llm.remaining == 1
    [call] = read_trace(result.trace_path, "llm_call")
    assert call["usd"] == "0.014"
    assert call["usage"]["input_tokens"] == 1000


async def test_monthly_cap_answer_names_the_monthly_setting(tmp_path: Path) -> None:
    result, _, _ = await run_agent(
        tmp_path, [], budget=make_budget(tmp_path, daily="5", monthly="0"), llm=ScriptedLLM([])
    )
    assert result.status == "budget_exceeded"
    assert "月次の上限" in result.answer
    assert "ECHOLAB_MONTHLY_USD" in result.answer and "caps_usd.monthly" in result.answer


async def test_tool_round_limit(tmp_path: Path) -> None:
    turns = [tool_turn(("damage_expected", DMG_A)) for _ in range(4)]
    result, llm, backend = await run_agent(tmp_path, turns, max_tool_rounds=3)
    assert result.status == "tool_round_limit"
    assert len(backend.calls) == 3
    assert not re.search(r"\d", result.answer)
    assert llm.remaining == 0


async def test_refusal_stops_without_running_tools(tmp_path: Path) -> None:
    result, _, backend = await run_agent(
        tmp_path,
        [tool_turn(("damage_expected", DMG_A), stop_reason="refusal")],
    )
    assert result.status == "refusal"
    assert backend.calls == []
    assert not re.search(r"\d", result.answer)


async def test_max_tokens_stops_without_running_truncated_tools(tmp_path: Path) -> None:
    result, _, backend = await run_agent(
        tmp_path,
        [tool_turn(("damage_expected", DMG_A), stop_reason="max_tokens")],
    )
    assert result.status == "max_tokens"
    assert backend.calls == []


async def test_empty_final_text_is_rejected(tmp_path: Path) -> None:
    result, _, _ = await run_agent(
        tmp_path, [{"text": ""}, {"text": "数値は必要ありませんでした。"}]
    )
    assert result.status == "answered"
    assert result.drafts_rejected == 1


async def test_llm_error_ends_the_run(tmp_path: Path) -> None:
    class Broken:
        model = "claude-opus-5-5"

        async def complete(self, **_: Any):
            raise LLMError("接続できません")

    result, _, _ = await run_agent(tmp_path, [], llm=Broken())
    assert result.status == "llm_error"
    assert read_trace(result.trace_path, "llm_error")


async def test_scripted_llm_rejects_unexpected_extra_calls(tmp_path: Path) -> None:
    with pytest.raises(ScriptExhausted):
        await run_agent(tmp_path, [tool_turn(("damage_expected", DMG_A))])
