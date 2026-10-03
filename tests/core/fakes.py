"""テスト用の偽のツールサービス。Java を起動せず、Python の参照実装で計算する。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from core.contracts import ToolEnvelope, ToolError, ToolSpec, to_wire_name
from tests.reference import calc_reference as ref

_CALCULATORS: dict[str, Callable[[dict], Mapping[str, object]]] = {
    "damage.expected": ref.damage_expected,
    "echo.score": ref.echo_score,
    "gacha.probability_within": lambda i: {"probability": ref.gacha_probability_within(i)},
}

_OPEN_SCHEMA: Mapping[str, Any] = {"type": "object"}

#: calc-engine の出力の桁（Java の ``Precision.round``：小数点以下 6 桁・HALF_EVEN）。
_OUTPUT_QUANTUM = Decimal("0.000001")


def _to_output(value: object) -> Decimal:
    """calc-engine と同じ形の値にする。

    Decimal（期待ダメージ・声骸のスコア）は小数点以下 6 桁に丸め、float（ガチャの確率）は
    最短の表現のまま（Java の ``BigDecimal.valueOf(double)`` と同じ）にする。
    """
    if isinstance(value, Decimal):
        return value.quantize(_OUTPUT_QUANTUM, rounding=ROUND_HALF_EVEN)
    return Decimal(repr(value))


class FakeCalcBackend:
    """calc-engine の代わり。

    入力はゴールデンケースの ``input`` と同じ形（データ参照は受け付けない）。
    """

    def __init__(self, unverified: Mapping[str, tuple[str, ...]] | None = None) -> None:
        #: ツール名 → 結果に付ける unverified_inputs（未確認データの伝搬を試すため）
        self.unverified = dict(unverified or {})
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=to_wire_name(t), description=f"{t}（テスト用）", input_schema=_OPEN_SCHEMA
            )
            for t in _CALCULATORS
        ]

    async def call_tool(self, wire_name: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        self.calls.append((wire_name, dict(arguments)))
        tool = next((t for t in _CALCULATORS if to_wire_name(t) == wire_name), None)
        if tool is None:
            raise ToolError(f"未知のツールです: {wire_name}")
        try:
            values = _CALCULATORS[tool](dict(arguments))
        except (KeyError, TypeError, ValueError, ArithmeticError) as e:
            raise ToolError(f"入力が不正です: {e}") from e
        return ToolEnvelope(
            tool=tool,
            values={k: _to_output(v) for k, v in values.items()},
            unverified_inputs=self.unverified.get(tool, ()),
        )

    async def aclose(self) -> None:
        self.closed = True
