"""比較ツールの計算と、LLM に見せるツール定義。

精度の方針は calc-engine（Java の ``Precision``）と同じにする。

- 途中の計算は有効桁 16 桁・ROUND_HALF_EVEN。
- 結果は小数 6 桁に丸める（ROUND_HALF_EVEN）。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Any

from core.contracts import SOURCE_ID, ToolError, ToolSpec, to_wire_name

#: 途中の計算の有効桁数。
PRECISION = 16
#: 結果の小数の桁数。
SCALE = Decimal("0.000001")
#: 丸めた結果の桁数は有効桁 16 を超えうるため、丸めは広い文脈で行う。
_QUANTIZE_CONTEXT = Context(prec=60, rounding=ROUND_HALF_EVEN)


def _quantize(x: Decimal) -> Decimal:
    q = x.quantize(SCALE, context=_QUANTIZE_CONTEXT)
    # 「-0.000000」を「0.000000」にそろえる
    return q.copy_abs() if q.is_zero() else q


def diff(a: Decimal, b: Decimal) -> dict[str, Decimal]:
    """差 ``a − b``。"""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        d = a - b
    return {"diff": _quantize(d)}


def ratio(a: Decimal, b: Decimal) -> dict[str, Decimal]:
    """比 ``a / b`` と増加率 ``a / b − 1``。

    :raises ToolError: ``b`` が 0 のとき。
    """
    if b.is_zero():
        raise ToolError("b が 0 のため、比を計算できません")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        r = a / b
        change = r - 1
    return {"ratio": _quantize(r), "change": _quantize(change)}


#: ドメインのツール名 → 計算の関数。
COMPARE_TOOLS: Mapping[str, Callable[[Decimal, Decimal], dict[str, Decimal]]] = {
    "compare.diff": diff,
    "compare.ratio": ratio,
}

_SOURCE_ID_SCHEMA: Mapping[str, Any] = {
    "type": "string",
    "pattern": SOURCE_ID.pattern,
    "description": "出典 ID（例 c1.total）。数値そのものは渡さない",
}

_INPUT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"a": _SOURCE_ID_SCHEMA, "b": _SOURCE_ID_SCHEMA},
    "required": ["a", "b"],
    "additionalProperties": False,
}

#: LLM に見せる比較ツールの定義（wire 名）。
COMPARE_SPECS: list[ToolSpec] = [
    ToolSpec(
        name=to_wire_name("compare.diff"),
        description=(
            "2 つの値の差 a − b を計算する（結果のフィールドは diff）。"
            "a・b には数値ではなく、これまでのツール結果の出典 ID（例 c1.total）を渡す。"
            "差を自分で計算せず、必ずこのツールを使うこと。"
        ),
        input_schema=_INPUT_SCHEMA,
    ),
    ToolSpec(
        name=to_wire_name("compare.ratio"),
        description=(
            "2 つの値の比 a / b（ratio）と増加率 a / b − 1（change）を計算する。"
            "a・b には数値ではなく、これまでのツール結果の出典 ID（例 c1.total）を渡す。"
            "「何 % 高いか」は change を [[cN.change|%1]] の形で引用する。"
            "比や割合を自分で計算せず、必ずこのツールを使うこと。"
        ),
        input_schema=_INPUT_SCHEMA,
    ),
]
