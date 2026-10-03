"""CLI と評価で共通の組み立て（ゲートウェイ・LLM・Agent）。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from core.agent.llm.base import LLM
from core.contracts import SourceValue

REPO_ROOT = Path(__file__).resolve().parents[2]


class CliError(Exception):
    """CLI の使い方の誤り（引数・台本など）。メッセージをそのまま利用者に見せる。"""


def startup_errors() -> tuple[type[BaseException], ...]:
    """設定・起動の誤り（CLI が終了コード 2 と短い説明で終える例外）。"""
    from core.agent.llm import ScriptExhausted, ScriptMismatch
    from core.gateway import BudgetConfigError, ServiceStartError, UnknownDomainError

    return (
        CliError,
        UnknownDomainError,
        ServiceStartError,
        BudgetConfigError,
        ScriptExhausted,
        ScriptMismatch,
    )


def report_cli_error(e: BaseException, *, debug: bool = False) -> int | None:
    """設定・起動の誤りなら説明を標準エラーに書いて終了コード 2 を返す。それ以外は None。

    ``debug`` のときはトレースバックも書く。
    """
    import sys
    import traceback

    from core.agent.llm import ScriptExhausted, ScriptMismatch

    if not isinstance(e, startup_errors()):
        return None
    if debug:
        traceback.print_exception(e, file=sys.stderr)
    message = str(e)
    if isinstance(e, ScriptExhausted | ScriptMismatch):
        message = (
            "台本どおりに進みませんでした"
            f"（質問・台本・--fake-backend の組み合わせを確かめてください）: {e}"
        )
    print(f"エラー: {message}", file=sys.stderr)
    if not debug:
        print("（--debug を付けるとトレースバックを表示します）", file=sys.stderr)
    return 2


def domain_services(repo_root: Path, domain: str) -> list[str]:
    """ドメインのツールが使うサービス名（``domain.yaml`` の ``tools[].service``）。"""
    from core.gateway.gateway import load_domain

    manifest = load_domain(repo_root, domain)
    return sorted({t["service"] for t in manifest.get("tools", []) if t.get("service")})


async def open_gateway(
    repo_root: Path,
    domain: str,
    *,
    fake_backend: bool = False,
    fake_unverified: Mapping[str, Sequence[str]] | None = None,
    budget: Any | None = None,
) -> Any:
    """ゲートウェイを開く。

    ``fake_backend`` のときは、Java を起動せずに試験用の偽の計算サービス
    （``tests/core/fakes.py``。Python の参照実装で計算する）をつなぐ。デモと評価の再現用。
    """
    from core.gateway import Budget, Gateway

    backends = None
    if fake_backend:
        from tests.core.fakes import FakeCalcBackend

        unverified = {k: tuple(v) for k, v in (fake_unverified or {}).items()}
        backends = {
            s: FakeCalcBackend(unverified=unverified) for s in domain_services(repo_root, domain)
        }
    if budget is None:
        budget = Budget.from_config(repo_root)
    return await Gateway.open(repo_root, domain, backends=backends, budget=budget)


def make_budget(llm_kind: str, repo_root: Path, scratch_dir: Path) -> Any:
    """LLM の種類に合ったコストの上限と台帳を作る。

    - ``anthropic``：本物の台帳（``config/budget.yaml``、既定 ``.echolab/costs.jsonl``）。
    - ``scripted``：台本の使用量は架空なので、本物の台帳には書かない。上限の設定は同じものを使い、
      台帳だけを ``scratch_dir`` の中の使い捨てのファイルにする（CLI と評価で同じ扱い）。
    """
    from core.gateway import Budget

    config = Budget.from_config(repo_root)
    if llm_kind == "anthropic":
        return config
    return Budget(
        Path(scratch_dir) / "costs.jsonl",
        config.daily_usd,
        config.monthly_usd,
        pricing=config.pricing,
    )


def make_llm(kind: str, *, script: Path | Sequence[Mapping[str, Any]] | None = None) -> LLM:
    """``anthropic``（実物の Claude）か ``scripted``（台本）の LLM を作る。"""
    from core.agent.llm import AnthropicLLM, ScriptedLLM

    if kind == "anthropic":
        return AnthropicLLM()
    if kind == "scripted":
        if script is None:
            raise ValueError("--llm scripted には台本（--script）が必要です")
        if isinstance(script, Path | str):
            path = Path(script)
            if not path.is_file():
                raise CliError(f"台本が見つかりません: {path}")
            try:
                return ScriptedLLM.from_file(path)
            except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as e:
                raise CliError(f"台本を読めません: {path}（{type(e).__name__}: {e}）") from e
        return ScriptedLLM(script)
    raise ValueError(f"未知の LLM です: {kind}")


def format_sources_table(cited: Sequence[SourceValue]) -> str:
    """引用した出典の表（CLI の出力）。"""
    if not cited:
        return "（引用した出典はありません）"
    header = ("出典 ID", "値", "ツール", "未確認データ")
    rows = [
        (s.source_id, str(s.value), s.tool, ", ".join(s.unverified_inputs) or "-") for s in cited
    ]
    widths = [max(_width(r[i]) for r in [header, *rows]) for i in range(len(header))]
    lines = []
    for n, row in enumerate([header, *rows]):
        lines.append("  ".join(_pad(c, w) for c, w in zip(row, widths, strict=True)).rstrip())
        if n == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _width(s: str) -> int:
    # 全角文字は 2 桁として数える（端末での桁をそろえるため）
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * (width - _width(s))
