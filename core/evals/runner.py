"""数値の忠実度の評価（ADR-0005・ADR-0007・ADR-0008）。

指標:

- **忠実度**：利用者に返した回答のうち、出典の無い数値を 1 つも含まないものの割合。
  検証に通った回答はテンプレートを検証器でもう一度検査し、定型の回答は数字を含まないことを確かめる。
  仕組み上 1.0 でなければならない。
- **差し戻し率**：下書きのうち、検証器が差し戻したものの割合。
- ケースごとの合否と、合計の費用。

``--llm scripted`` は台本で LLM を置き換え、試験用の偽の計算サービスで動かす
（API キー・Java 不要）。
``--llm anthropic`` は台本を使わず質問だけを実物の Claude に渡し、実物の計算サービスを使う。
"""

from __future__ import annotations

import json
import re
import tempfile
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from core.agent.llm import ScriptedLLM
from core.agent.loop import Agent, AgentResult, load_system_prompt
from core.agent.runtime import REPO_ROOT, make_budget, make_llm, open_gateway
from core.contracts import UNVERIFIED_NOTE

DEFAULT_CASES = Path("evals/faithfulness/cases.yaml")
DEFAULT_RAW_DIR = Path("evals/reports/raw")
_DIGITS = re.compile(r"\d+")


class UnknownCaseError(ValueError):
    """``--case`` で指定したケース ID が、ケースのファイルに無い。"""


@dataclass
class CaseResult:
    case_id: str
    title: str
    status: str
    passed: bool
    faithful: bool
    failures: list[str] = field(default_factory=list)
    drafts: int = 0
    drafts_rejected: int = 0
    cited: list[str] = field(default_factory=list)
    cost_usd: Decimal = Decimal(0)
    run_id: str | None = None
    answer: str = ""


@dataclass
class EvalReport:
    llm: str
    cases_path: str
    results: list[CaseResult]

    @property
    def faithfulness(self) -> float:
        answered = len(self.results)
        return sum(r.faithful for r in self.results) / answered if answered else 1.0

    @property
    def draft_rejection_rate(self) -> float:
        drafts = sum(r.drafts for r in self.results)
        return sum(r.drafts_rejected for r in self.results) / drafts if drafts else 0.0

    @property
    def passed(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def total_cost(self) -> Decimal:
        return sum((r.cost_usd for r in self.results), Decimal(0))

    @property
    def ok(self) -> bool:
        return self.passed == len(self.results) and self.faithfulness == 1.0


def load_cases(path: Path) -> list[dict[str, Any]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = doc["cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"ケース ID が重複しています: {path}")
    return cases


def unsourced_numbers(result: AgentResult, question: str, sources: Mapping[str, Any]) -> int:
    """回答に含まれる、出典の無い数値の数（忠実度の判定）。"""
    from core.verifier import verify

    if result.status == "answered":
        # 検証済みの回答も、テンプレートをもう一度検査して数え直す
        if result.template is None:
            return 1
        return len(verify(result.template, question, sources).problems)
    answer = result.answer
    if result.status == "budget_exceeded":
        # 上限の回答の金額は台帳と設定から決まる値（LLM は書いていない）なので数えない
        answer = re.sub(r"（使用額 [^）]*）", "", answer)
    return len(_DIGITS.findall(unicodedata.normalize("NFKC", answer)))


async def run_case(
    case: Mapping[str, Any],
    *,
    llm_kind: str,
    repo_root: Path,
    trace_dir: Path,
    budget: Any,
    domain: str = "wuwa",
) -> CaseResult:
    """1 ケースを実行して、期待と照合する。"""
    scripted = llm_kind == "scripted"
    llm = ScriptedLLM(case["turns"]) if scripted else make_llm(llm_kind)
    gw = await open_gateway(
        repo_root,
        domain,
        fake_backend=scripted,
        fake_unverified=case.get("fake_unverified"),
        budget=budget,
    )
    failures: list[str] = []
    try:
        agent = Agent(
            gateway=gw,
            llm=llm,
            system_prompt=load_system_prompt(repo_root, domain),
            trace_dir=trace_dir,
            domain=domain,
        )
        try:
            result = await agent.ask(case["question"])
        except AssertionError as e:  # 台本の使い切り・期待の不一致
            return CaseResult(
                case_id=case["id"],
                title=case.get("title", ""),
                status="error",
                passed=False,
                faithful=False,
                failures=[f"台本どおりに進みませんでした: {e}"],
            )
        unsourced = unsourced_numbers(result, case["question"], gw.sources)
    finally:
        await gw.aclose()

    expect = case.get("expect") or {}
    if unsourced:
        failures.append(f"出典の無い数値が {unsourced} 個あります")
    if "status" in expect and result.status != expect["status"]:
        failures.append(f"状態が {result.status}（期待 {expect['status']}）")
    note = UNVERIFIED_NOTE in result.answer
    expected_note = expect.get("unverified_note")
    if expected_note is not None and result.status == "answered" and note != bool(expected_note):
        failures.append(f"未確認データの注記が{'ある' if note else 'ない'}")
    cited = [s.source_id for s in result.cited]
    if scripted:
        if "cited" in expect and sorted(cited) != sorted(expect["cited"]):
            failures.append(f"引用した出典が {cited}（期待 {expect['cited']}）")
        if "drafts_rejected" in expect and result.drafts_rejected != expect["drafts_rejected"]:
            failures.append(
                f"差し戻しが {result.drafts_rejected} 回（期待 {expect['drafts_rejected']} 回）"
            )
        if isinstance(llm, ScriptedLLM) and llm.remaining:
            failures.append(f"台本の応答が {llm.remaining} 件余りました")

    return CaseResult(
        case_id=case["id"],
        title=case.get("title", ""),
        status=result.status,
        passed=not failures,
        faithful=unsourced == 0,
        failures=failures,
        drafts=result.drafts,
        drafts_rejected=result.drafts_rejected,
        cited=cited,
        cost_usd=result.cost_usd,
        run_id=result.run_id,
        answer=result.answer,
    )


async def run_evals(
    *,
    llm_kind: str = "scripted",
    cases_path: Path = DEFAULT_CASES,
    repo_root: Path = REPO_ROOT,
    raw_dir: Path = DEFAULT_RAW_DIR,
    only: Sequence[str] | None = None,
) -> EvalReport:
    """全ケースを順に実行する（実物の LLM では費用が出るので並列にしない）。"""
    cases_path = cases_path if cases_path.is_absolute() else repo_root / cases_path
    raw_dir = raw_dir if raw_dir.is_absolute() else repo_root / raw_dir
    all_cases = load_cases(cases_path)
    if only:
        known = [c["id"] for c in all_cases]
        unknown = [c for c in only if c not in known]
        if unknown:
            raise UnknownCaseError(
                f"ケースが見つかりません: {', '.join(unknown)}"
                f"（{cases_path.name} のケース: {', '.join(known)}）"
            )
    cases = [c for c in all_cases if not only or c["id"] in only]
    trace_dir = raw_dir / "traces"
    results: list[CaseResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        budget = make_budget(llm_kind, repo_root, Path(tmp))
        for case in cases:
            results.append(
                await run_case(
                    case,
                    llm_kind=llm_kind,
                    repo_root=repo_root,
                    trace_dir=trace_dir,
                    budget=budget,
                )
            )
    try:
        shown = str(cases_path.relative_to(repo_root))
    except ValueError:
        shown = str(cases_path)
    report = EvalReport(llm=llm_kind, cases_path=shown, results=results)
    _write_raw(report, raw_dir)
    return report


def _write_raw(report: EvalReport, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    path = raw_dir / f"faithfulness-{report.llm}-{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in report.results:
            row = {**r.__dict__, "cost_usd": str(r.cost_usd)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_markdown(report: EvalReport, *, model: str | None = None) -> str:
    """コミットする集計レポート（生の記録は evals/reports/raw/ に残す）。"""
    today = datetime.now(UTC).date().isoformat()
    lines = [
        "# 評価レポート：数値の忠実度",
        "",
        f"- 日付（UTC）: {today}",
        f"- LLM: `{report.llm}`" + (f"（`{model}`）" if model else ""),
        f"- ケース: `{report.cases_path}`（{len(report.results)} 件）",
        "",
        "## 指標",
        "",
        "| 指標 | 値 |",
        "|---|---|",
        f"| 忠実度（出典の無い数値を含まない回答の割合） | {report.faithfulness:.3f} |",
        f"| 差し戻し率（差し戻した下書き / 下書き） | {report.draft_rejection_rate:.3f}"
        f"（{sum(r.drafts_rejected for r in report.results)} / "
        f"{sum(r.drafts for r in report.results)}） |",
        f"| 合格したケース | {report.passed} / {len(report.results)} |",
        f"| 費用の合計（USD） | {report.total_cost:.6f} |",
        "",
        "## ケースごとの結果",
        "",
        "| ケース | 内容 | 状態 | 下書き | 差し戻し | 引用した出典 | 合否 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report.results:
        cited = ", ".join(f"`{c}`" for c in r.cited) or "-"
        verdict = "合格" if r.passed else "不合格：" + "；".join(r.failures)
        lines.append(
            f"| `{r.case_id}` | {r.title} | {r.status} | {r.drafts} | {r.drafts_rejected} "
            f"| {cited} | {verdict} |"
        )
    if report.llm == "scripted":
        lines += [
            "",
            "台本モードの使用量（トークン数）は台本に書いた架空の値で、費用は計算の確認用です。",
        ]
    return "\n".join(lines) + "\n"
