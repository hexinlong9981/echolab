"""評価（数値の忠実度）。``python -m core.evals`` で実行する。"""

from core.evals.runner import (
    CaseResult,
    EvalReport,
    UnknownCaseError,
    load_cases,
    render_markdown,
    run_case,
    run_evals,
    unsourced_numbers,
)

__all__ = [
    "CaseResult",
    "EvalReport",
    "UnknownCaseError",
    "load_cases",
    "render_markdown",
    "run_case",
    "run_evals",
    "unsourced_numbers",
]
