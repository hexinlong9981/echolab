"""CLI：``python -m core.evals [--llm scripted|anthropic] [--out evals/reports/<name>.md]``

存在しないケース ID（``--case``）や設定の誤りは、短い説明を表示して終了コード 2 で終える。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from core.agent.runtime import REPO_ROOT, CliError, report_cli_error
from core.evals.runner import (
    DEFAULT_CASES,
    DEFAULT_RAW_DIR,
    UnknownCaseError,
    render_markdown,
    run_evals,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m core.evals", description="数値の忠実度を評価する")
    p.add_argument("--llm", choices=["scripted", "anthropic"], default="scripted")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--out", type=Path, help="集計レポート（Markdown）の出力先")
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="生の記録の保存先")
    p.add_argument("--case", action="append", dest="only", help="このケースだけを実行する")
    p.add_argument(
        "--debug", action="store_true", help="設定・起動の誤りでもトレースバックを表示する"
    )
    args = p.parse_args(argv)

    try:
        cases = args.cases if args.cases.is_absolute() else REPO_ROOT / args.cases
        if not cases.is_file():
            raise CliError(f"ケースのファイルが見つかりません: {cases}")
        report = asyncio.run(
            run_evals(llm_kind=args.llm, cases_path=cases, raw_dir=args.raw_dir, only=args.only)
        )
    except UnknownCaseError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        code = report_cli_error(e, debug=args.debug)
        if code is None:
            raise
        return code
    model = None
    if args.llm == "anthropic":
        from core.agent.llm.claude import DEFAULT_MODEL

        model = DEFAULT_MODEL
    text = render_markdown(report, model=model)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
