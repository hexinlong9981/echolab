"""評価（数値の忠実度）を台本モードで実行する。CI で毎回通す。"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from core.agent.loop import AgentResult
from core.evals import load_cases, render_markdown, run_evals, unsourced_numbers
from core.evals.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals/faithfulness/cases.yaml"


async def test_all_scripted_cases_pass(tmp_path: Path) -> None:
    report = await run_evals(llm_kind="scripted", raw_dir=tmp_path / "raw")
    failures = {r.case_id: r.failures for r in report.results if not r.passed}
    assert failures == {}
    assert report.faithfulness == 1.0
    assert report.ok
    statuses = {r.case_id: r.status for r in report.results}
    assert statuses["never-corrected"] == "fallback"
    assert sum(r.drafts_rejected for r in report.results) >= 4
    assert 0 < report.draft_rejection_rate < 1
    assert report.total_cost > 0  # 台本の使用量から費用を計算している

    # 生の記録とトレースは raw に残る（コミットしない）
    assert list((tmp_path / "raw").glob("faithfulness-scripted-*.jsonl"))
    assert len(list((tmp_path / "raw/traces").glob("*.jsonl"))) == len(report.results)

    text = render_markdown(report)
    assert "| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |" in text
    assert f"| 合格したケース | {len(report.results)} / {len(report.results)} |" in text


def test_cases_cover_the_required_scenarios() -> None:
    cases = load_cases(CASES)
    assert 8 <= len(cases) <= 12
    ids = {c["id"] for c in cases}
    assert {"never-corrected", "gacha-unverified", "compare-builds"} <= ids
    tools = {u["name"] for c in cases for t in c["turns"] for u in t.get("tool_uses") or ()}
    assert {"damage_expected", "echo_score", "gacha_probability_within"} <= tools
    assert {"compare_diff", "compare_ratio"} <= tools
    assert any(c.get("fake_unverified") for c in cases)
    assert sum(c["expect"].get("drafts_rejected", 0) > 0 for c in cases) >= 3


async def test_a_failing_expectation_is_reported(tmp_path: Path) -> None:
    import yaml

    doc = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    case = next(c for c in doc["cases"] if c["id"] == "damage-basic")
    case["expect"]["drafts_rejected"] = 1
    case["turns"].append({"text": "余り"})
    path = tmp_path / "cases.yaml"
    path.write_text(yaml.safe_dump({"cases": [case]}, allow_unicode=True), encoding="utf-8")
    report = await run_evals(llm_kind="scripted", cases_path=path, raw_dir=tmp_path / "raw")
    [result] = report.results
    assert not result.passed and not report.ok
    assert any("差し戻し" in f for f in result.failures)
    assert any("余り" in f for f in result.failures)
    assert result.faithful  # 期待とずれても、回答そのものは忠実


def test_unsourced_numbers_counts_digits_in_unverified_answers(tmp_path: Path) -> None:
    def result(status: str, answer: str, template: str | None = None) -> AgentResult:
        return AgentResult(
            answer=answer, status=status, run_id="r", trace_path=tmp_path, template=template
        )

    assert unsourced_numbers(result("fallback", "数値はありません"), "q", {}) == 0
    assert unsourced_numbers(result("fallback", "答えは 42 と ４２"), "q", {}) == 2
    assert unsourced_numbers(result("answered", "42", template="42"), "q", {}) == 1
    assert unsourced_numbers(result("answered", "42", template="42"), "42 は？", {}) == 0


def test_cli_writes_markdown_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "report.md"
    code = main(["--out", str(out), "--raw-dir", str(tmp_path / "raw"), "--case", "echo-score"])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 評価レポート：数値の忠実度")
    assert "`echo-score`" in text and "`damage-basic`" not in text
    assert text in capsys.readouterr().out


def test_committed_baseline_report_is_up_to_date() -> None:
    """コミットしたベースラインの指標が、現在の台本の結果と一致する（日付を除く）。"""
    baseline = (ROOT / "evals/reports/scripted-baseline.md").read_text(encoding="utf-8")
    assert "| 忠実度（出典の無い数値を含まない回答の割合） | 1.000 |" in baseline
    cases = load_cases(CASES)
    for case in cases:
        assert re.search(rf"\| `{re.escape(case['id'])}` \|.*\| 合格 \|", baseline), case["id"]


def test_cli_rejects_unknown_case_ids(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--raw-dir", str(tmp_path / "raw"), "--case", "echo-score", "--case", "nope"])
    err = capsys.readouterr().err
    assert code == 2
    assert "ケースが見つかりません: nope" in err
    assert "damage-basic" in err  # 使えるケース ID を示す
    assert not (tmp_path / "raw").exists()  # 1 件も実行しない


def test_budget_amounts_are_not_counted_as_unsourced(tmp_path: Path) -> None:
    from core.agent.loop import budget_answer
    from core.contracts import BudgetExceeded

    answer = budget_answer(
        BudgetExceeded("x", period="daily", spent=Decimal("1.02"), cap=Decimal("1.00"))
    )
    result = AgentResult(answer=answer, status="budget_exceeded", run_id="r", trace_path=tmp_path)
    assert "1.02" in answer
    assert unsourced_numbers(result, "q", {}) == 0
