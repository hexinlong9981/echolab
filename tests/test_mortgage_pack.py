"""住宅ローンのパック（domains/mortgage、ADR-0009）の試験。

- パックの実装（calc/loan.py、Decimal）をゴールデンケースと照合する（参照実装との照合は
  tests/test_golden_reference.py）。
- パックの MCP サーバ（python -m domains.mortgage.calc）を、コアのゲートウェイから
  config/services.yaml どおりに起動して呼ぶ。Java は要らないので CI の python ジョブで毎回通す。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.agent import Agent, load_answer_note, load_system_prompt
from core.agent.llm import ScriptedLLM
from core.gateway import Budget, Gateway
from domains.mortgage.calc import loan

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "domains/mortgage"
LOAN = {"principal": 30000000, "annual_rate": 0.015, "years": 35}
PREPAY = {**LOAN, "after_months": 60, "prepay_amount": 3000000, "method": "shorten_term"}


def _golden() -> list[tuple[str, dict]]:
    cases = []
    for path in sorted((PACK / "golden").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.extend((doc["tool"], c) for c in doc["cases"])
    return cases


def test_every_declared_tool_has_an_implementation_and_golden_cases() -> None:
    manifest = yaml.safe_load((PACK / "domain.yaml").read_text(encoding="utf-8"))
    declared = {t["name"] for t in manifest["tools"]}
    assert declared == set(loan.TOOLS)
    assert {tool for tool, _ in _golden()} == declared
    # 期待値が参照実装の出力だけにならないこと（循環を避ける）
    for tool in declared:
        assert any(c["derivation"] != "reference" for t, c in _golden() if t == tool), tool


@pytest.mark.parametrize(
    ("tool", "case"), _golden(), ids=lambda x: x["id"] if isinstance(x, dict) else x
)
def test_pack_implementation_matches_golden(tool: str, case: dict) -> None:
    actual = loan.TOOLS[tool](case["input"])
    assert set(actual) == set(case["expected"])
    for field, expected in case["expected"].items():
        assert float(actual[field]) == pytest.approx(expected, abs=case["tolerance"]), field
        assert actual[field] == actual[field].quantize(Decimal("0.000001"))  # 出力は小数 6 桁


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("mortgage.equal_payment", {**LOAN, "principal": 0}, "principal は 0 より大きい"),
        ("mortgage.equal_payment", {**LOAN, "annual_rate": 0.5}, "annual_rate は 0 以上"),
        ("mortgage.equal_payment", {**LOAN, "years": 2.5}, "years は整数"),
        ("mortgage.equal_payment", {**LOAN, "years": 51}, "years は 50 以下"),
        ("mortgage.equal_principal", {"principal": 1, "annual_rate": 0}, "years がありません"),
        ("mortgage.equal_payment", {**LOAN, "principal": True}, "principal は数値"),
        ("mortgage.prepayment", {**PREPAY, "after_months": 420}, "返済回数 420 より小さく"),
        ("mortgage.prepayment", {**PREPAY, "prepay_amount": 3e7}, "残高以上"),
        ("mortgage.prepayment", {**PREPAY, "method": "both"}, "method は"),
    ],
)
def test_invalid_inputs_are_explained(tool: str, arguments: dict, message: str) -> None:
    with pytest.raises(loan.LoanInputError, match=message):
        loan.TOOLS[tool](arguments)


def test_prepayment_saves_more_interest_when_shortening_the_term() -> None:
    shorten = loan.prepayment(PREPAY)
    reduce = loan.prepayment({**PREPAY, "method": "reduce_payment"})
    assert shorten["balance_before"] == reduce["balance_before"]
    assert shorten["interest_saved"] > reduce["interest_saved"] > 0
    assert shorten["months_saved"] > 0 and reduce["months_saved"] == 0
    assert reduce["monthly_payment_after"] < shorten["monthly_payment_after"]


def test_equal_principal_pays_less_interest_than_equal_payment() -> None:
    assert loan.equal_principal(LOAN)["total_interest"] < loan.equal_payment(LOAN)["total_interest"]


# ---------------------------------------------------------------------------
# MCP サーバ（実物の子プロセス）
# ---------------------------------------------------------------------------


def _budget(tmp_path: Path) -> Budget:
    return Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))


async def test_gateway_starts_the_pack_server_and_runs_golden_cases(tmp_path: Path) -> None:
    async with await Gateway.open(ROOT, "mortgage", budget=_budget(tmp_path)) as gw:
        names = sorted(s.name for s in gw.tool_specs())
        assert names == [
            "compare_diff",
            "compare_ratio",
            "mortgage_equal_payment",
            "mortgage_equal_principal",
            "mortgage_prepayment",
        ]
        for tool, case in _golden():
            outcome = await gw.call(tool.replace(".", "_"), case["input"])
            assert outcome.error is None, (case["id"], outcome.error)
            values = {s.source_id.split(".", 1)[1]: s.value for s in outcome.sources}
            for field, expected in case["expected"].items():
                assert float(values[field]) == pytest.approx(expected, abs=case["tolerance"])


async def test_pack_server_errors_reach_the_llm_as_tool_errors(tmp_path: Path) -> None:
    async with await Gateway.open(ROOT, "mortgage", budget=_budget(tmp_path)) as gw:
        # スキーマ違反はゲートウェイが止める（サーバを呼ばない）
        bad_schema = await gw.call("mortgage_equal_payment", {**LOAN, "years": 0})
        assert bad_schema.error is not None and bad_schema.error.startswith("入力が不正です")
        # 計算の前提に合わない入力は、サーバが日本語の説明を返す
        too_much = await gw.call("mortgage_prepayment", {**PREPAY, "prepay_amount": 3e7})
        assert too_much.error is not None and "残高以上" in too_much.error
        # 宣言していないツール（鳴潮のツール）は見えない
        assert (await gw.call("damage_expected", {})).error is not None


async def test_agent_answers_with_the_pack_server_and_adds_the_disclaimer(tmp_path: Path) -> None:
    script = yaml.safe_load((PACK / "examples/compare_methods.yaml").read_text(encoding="utf-8"))
    async with await Gateway.open(ROOT, "mortgage", budget=_budget(tmp_path)) as gw:
        agent = Agent(
            gateway=gw,
            llm=ScriptedLLM(script["turns"]),
            system_prompt=load_system_prompt(ROOT, "mortgage"),
            trace_dir=tmp_path / "traces",
            domain="mortgage",
            answer_note=load_answer_note(ROOT, "mortgage"),
        )
        result = await agent.ask("元利均等と元金均等では利息の合計はどれだけ違う？")
    assert result.status == "answered"
    assert "差：685,489 円" in result.answer
    assert result.answer.endswith(
        "金融上の助言ではありません。実際の返済額は金融機関にご確認ください。"
    )
    assert [s.source_id for s in result.cited][-1] == "c3.diff"
    assert "住宅ローン" in agent.system_prompt and "鳴潮" not in agent.system_prompt


# ---------------------------------------------------------------------------
# 評価（台本モード）
# ---------------------------------------------------------------------------

CASES = ROOT / "evals/faithfulness/mortgage.yaml"
BASELINE = ROOT / "evals/reports/scripted-baseline-mortgage.md"


async def test_scripted_evals_pass(tmp_path: Path) -> None:
    from core.evals import run_evals

    report = await run_evals(llm_kind="scripted", cases_path=CASES, raw_dir=tmp_path / "raw")
    assert report.domain == "mortgage"
    assert {r.case_id: r.failures for r in report.results if not r.passed} == {}
    assert report.faithfulness == 1.0 and report.ok
    statuses = {r.case_id: r.status for r in report.results}
    assert statuses["never-corrected"] == "fallback"


def test_committed_baseline_report_is_up_to_date() -> None:
    import re

    from core.evals import load_cases

    baseline = BASELINE.read_text(encoding="utf-8")
    assert "- ドメイン: `mortgage`" in baseline
    assert "| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |" in baseline
    for case in load_cases(CASES):
        assert re.search(rf"\| `{re.escape(case['id'])}` \|.*\| 合格 \|", baseline), case["id"]
