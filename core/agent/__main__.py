"""CLI：``python -m core.agent "質問" [--domain wuwa] [--llm anthropic|scripted] ...``

既定は実物の Claude と、``config/services.yaml`` で起動する計算サービス（MCP）。
台本モード（``--llm scripted --script 台本.yaml``）は API キー無しで動き、
``--fake-backend`` を付けると Java も起動しない（デモ用）。

設定・使い方の誤り（ドメインが無い、台本が無い、java や jar が無い、上限の設定が不正など）は、
トレースバックではなく短い説明と直し方を表示して、終了コード 2 で終える（``--debug`` で
トレースバックも表示する）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

from core.agent.loop import Agent, AgentResult, load_answer_note, load_system_prompt
from core.agent.runtime import (
    REPO_ROOT,
    CliError,
    format_sources_table,
    make_budget,
    make_llm,
    open_gateway,
    report_cli_error,
)
from core.trace import DEFAULT_TRACE_DIR

EPILOG = """\
コストの台帳:
  --llm anthropic は実際の費用を本物の台帳（既定 .echolab/costs.jsonl）に記録し、
  日次・月次の上限（config/budget.yaml、環境変数 ECHOLAB_DAILY_USD・ECHOLAB_MONTHLY_USD）を守る。
  --llm scripted の使用量は台本に書いた架空の値なので、実行ごとの使い捨ての台帳に記録し、
  本物の台帳には書かない（評価 python -m core.evals と同じ扱い）。

終了コード:
  0 回答した / 1 回答できなかった（定型の回答で終えた）/ 2 設定・使い方の誤り
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m core.agent",
        description="出典付きで質問に答える",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("question", help="質問（例：攻撃力 2000 のときの期待ダメージは？）")
    p.add_argument("--domain", default="wuwa", help="ドメインパック（既定 wuwa）")
    p.add_argument(
        "--llm",
        choices=["anthropic", "scripted"],
        default="anthropic",
        help="anthropic（実物の Claude。既定）か scripted（台本。API キー不要）",
    )
    p.add_argument("--script", type=Path, help="--llm scripted の台本（YAML）")
    p.add_argument(
        "--fake-backend",
        action="store_true",
        help="計算サービスの代わりに試験用の偽物（Python の参照実装）を使う",
    )
    p.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR, help="トレースの保存先")
    p.add_argument(
        "--debug", action="store_true", help="設定・起動の誤りでもトレースバックを表示する"
    )
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    return p


async def run(args: argparse.Namespace) -> AgentResult:
    from core.gateway.gateway import load_domain

    if args.llm == "scripted" and args.script is None:
        raise CliError("--llm scripted には --script（台本の YAML）が必要です")
    load_domain(args.repo_root, args.domain)  # ドメインの有無はここで確かめる（偽物でも同じ）
    llm = make_llm(args.llm, script=args.script)
    trace_dir = args.trace_dir if args.trace_dir.is_absolute() else args.repo_root / args.trace_dir
    with tempfile.TemporaryDirectory(prefix="echolab-") as scratch:
        budget = make_budget(args.llm, args.repo_root, Path(scratch))
        gw = await open_gateway(
            args.repo_root, args.domain, fake_backend=args.fake_backend, budget=budget
        )
        try:
            agent = Agent(
                gateway=gw,
                llm=llm,
                system_prompt=load_system_prompt(args.repo_root, args.domain),
                trace_dir=trace_dir,
                domain=args.domain,
                answer_note=load_answer_note(args.repo_root, args.domain),
            )
            return await agent.ask(args.question)
        finally:
            await gw.aclose()


def render_result(result: AgentResult) -> str:
    lines = [result.answer, "", "出典:", format_sources_table(result.cited), ""]
    lines.append(
        f"状態: {result.status}　差し戻し: {result.drafts_rejected} 回　"
        f"費用: ${result.cost_usd:.4f}　実行 ID: {result.run_id}"
    )
    lines.append(f"トレース: {result.trace_path}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(run(args))
    except Exception as e:
        code = report_cli_error(e, debug=args.debug)
        if code is None:
            raise
        return code
    print(render_result(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
