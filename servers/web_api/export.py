"""公開する回放と評価のダッシュボードのデータを書き出す（M5・ADR-0011）。

    python -m servers.web_api.export [--out web/public/data]

台本モード（API キー不要）で、デモ 3 件と評価のケースをすべて実行し、次を書き出す。

- ``index.json``：デモの一覧と、評価ごとの指標・ケースの結果（どのトレースかも含む）
- ``runs/<実行 ID>.json``：1 回の質問の結果と実行トレースの出来事

計算サービスは試験用の偽物（Python の参照実装・OCR の記録）を使う。Java も Tesseract も要らず、
何度実行しても同じ内容になる。手元の絶対パスは書き出さない。CI が生成し、web/ のビルドに含める。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.agent.runtime import REPO_ROOT
from core.evals import run_evals
from servers.web_api.runner import DEMOS, ask, run_record

#: 評価（ケースのファイルと表示名）。
SUITES: tuple[dict[str, str], ...] = (
    {
        "id": "faithfulness",
        "title": "数値の忠実度（鳴潮）",
        "cases": "evals/faithfulness/cases.yaml",
    },
    {
        "id": "mortgage",
        "title": "数値の忠実度（住宅ローン）",
        "cases": "evals/faithfulness/mortgage.yaml",
    },
    {
        "id": "redteam",
        "title": "注入（プロンプトインジェクション）",
        "cases": "evals/redteam/cases.yaml",
    },
)

DEFAULT_OUT = Path("web/public/data")


async def export(out: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    (out / "runs").mkdir(parents=True)
    index: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA"),
        "demos": [],
        "suites": [],
        "services": tool_services(repo_root),
    }
    with tempfile.TemporaryDirectory(prefix="echolab-export-") as tmp:
        tmp_dir = Path(tmp)
        for demo in DEMOS:
            record = await ask(
                demo["question"],
                domain=demo["domain"],
                llm_kind="scripted",
                script=repo_root / demo["script"],
                fake_backend=True,
                trace_dir=tmp_dir / "demos",
                repo_root=repo_root,
            )
            _write(out / "runs" / f"{record['run_id']}.json", record)
            index["demos"].append({**demo, "run_id": record["run_id"], "status": record["status"]})

        for suite in SUITES:
            raw = tmp_dir / suite["id"]
            report = await run_evals(
                llm_kind="scripted",
                cases_path=repo_root / suite["cases"],
                repo_root=repo_root,
                raw_dir=raw,
            )
            cases = []
            for r in report.results:
                if r.run_id:
                    trace = raw / "traces" / f"{r.run_id}.jsonl"
                    record = run_record(trace, repo_root=repo_root, fake_backend=True)
                    _write(out / "runs" / f"{r.run_id}.json", record)
                cases.append(
                    {
                        "id": r.case_id,
                        "title": r.title,
                        "status": r.status,
                        "passed": r.passed,
                        "faithful": r.faithful,
                        "drafts": r.drafts,
                        "drafts_rejected": r.drafts_rejected,
                        "tool_errors": r.tool_errors,
                        "cited": r.cited,
                        "failures": r.failures,
                        "run_id": r.run_id,
                    }
                )
            index["suites"].append(
                {
                    **suite,
                    "domain": report.domain,
                    "faithfulness": report.faithfulness,
                    "draft_rejection_rate": report.draft_rejection_rate,
                    "passed": report.passed,
                    "total": len(report.results),
                    "tool_errors": report.tool_errors,
                    "ok": report.ok,
                    "cases": cases,
                }
            )
    _write(out / "index.json", index)
    return index


def tool_services(repo_root: Path) -> dict[str, str]:
    """ツール名 → それを受け持つサービス（回放の図で、どの箱に届いたかを示すため）。"""
    import yaml

    from core.compare import COMPARE_TOOLS

    services = {tool: "core" for tool in COMPARE_TOOLS}
    for manifest in sorted((repo_root / "domains").glob("*/domain.yaml")):
        for t in yaml.safe_load(manifest.read_text(encoding="utf-8")).get("tools") or []:
            services[t["name"]] = t["service"]
    return services


def _write(path: Path, doc: Any) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Web UI の回放・評価のデータを書き出す")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    index = asyncio.run(export(out))
    runs = len(list((out / "runs").glob("*.json")))
    bad = [s["id"] for s in index["suites"] if not s["ok"]]
    print(f"{out}: デモ {len(index['demos'])} 件・評価 {len(index['suites'])} 種・実行 {runs} 件")
    if bad:
        print(f"エラー: 評価が合格していません: {', '.join(bad)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
