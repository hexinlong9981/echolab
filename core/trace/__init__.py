"""実行トレース（ADR-0008）。1 回の質問を 1 つの JSONL ファイルに記録する。

ファイルは ``<trace_dir>/<run_id>.jsonl``（既定は ``.echolab/traces/``、Git の管理外）。
1 行が 1 つの出来事で、どの行にも ``ts``（UTC の ISO 8601）・``run_id``・``event`` が入る。

出来事の種類:

| event | 内容 |
|---|---|
| ``question`` | 質問・ドメイン・LLM の種類 |
| ``llm_call`` | 停止理由・トークン数・費用（USD） |
| ``tool_call`` | LLM が求めたツール呼び出し（wire 名と入力） |
| ``tool_result`` | ゲートウェイの結果（:class:`~core.contracts.CallOutcome`） |
| ``verdict`` | 検証器の判定（下書きごと） |
| ``answer`` | 利用者に返した回答と、その状態 |
| ``budget_exceeded`` | コストの上限で LLM を呼ばずに止めた |
| ``llm_error`` | LLM の呼び出しに失敗した（認証・通信・API のエラー） |
"""

from __future__ import annotations

import dataclasses
import json
import secrets
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_TRACE_DIR", "TraceWriter", "new_run_id", "read_trace", "to_jsonable"]

#: 既定の保存先（リポジトリ直下からの相対パス）。
DEFAULT_TRACE_DIR = Path(".echolab/traces")


def new_run_id() -> str:
    """実行 ID。時刻順に並び、同じ秒の実行とも衝突しない（例 ``20261003T120000Z-1a2b3c``）。"""
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"


def to_jsonable(obj: Any) -> Any:
    """トレースに書ける形に変える。Decimal は丸めずに文字列にする。"""
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set | frozenset):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    # SDK の応答ブロック（pydantic のモデル）
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return to_jsonable(model_dump(mode="json", exclude_none=True))
    return repr(obj)


class TraceWriter:
    """1 回の実行のトレースを書く。出来事ごとに追記してフラッシュする（途中で落ちても残る）。"""

    def __init__(
        self,
        trace_dir: Path | str,
        run_id: str | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.run_id = run_id or new_run_id()
        self.path = Path(trace_dir) / f"{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.on_event = on_event

    def emit(self, event: str, **data: Any) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "event": event,
            **{k: to_jsonable(v) for k, v in data.items()},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")
        if self.on_event is not None:
            self.on_event(record)


def read_trace(path: Path | str, event: str | None = None) -> list[dict[str, Any]]:
    """トレースを読む。``event`` を与えると、その種類の出来事だけを返す。"""
    return [r for r in _iter_records(Path(path)) if event is None or r["event"] == event]


def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
