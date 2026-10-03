"""プレースホルダを数値に置き換えるレンダラ。

書式（``contracts.PLACEHOLDER``）:

- 省略: 小数 2 桁まで（末尾の 0 と小数点は落とす）。``6192.0`` → ``6,192``
- ``N``: 小数 N 桁。``[[c1.total|1]]`` → ``6,192.0``
- ``%N``: 100 倍して小数 N 桁 + ``%``。``[[c2.change|%1]]`` → ``12.3%``

整数部は 3 桁ごとに ``,`` で区切る。丸めは ROUND_HALF_EVEN。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Context, Decimal

from core.contracts import PLACEHOLDER, SourceValue

#: ``[[ ... ]]`` の形をしたもの（形式が正しいかは問わない）。
BRACKETS = re.compile(r"\[\[(?P<body>.*?)\]\]")

#: 表示の丸めは桁数の大きい値でも失敗しないよう、広い文脈で行う。
_CONTEXT = Context(prec=60, rounding=ROUND_HALF_EVEN)

_DEFAULT_DECIMALS = 2


def format_value(value: Decimal, fmt: str | None) -> str:
    """1 つの値を書式に従って文字列にする。

    :raises ValueError: 書式が不正なとき。
    """
    percent = False
    if fmt is None:
        decimals, strip = _DEFAULT_DECIMALS, True
    else:
        m = re.fullmatch(r"(%?)([0-9])", fmt)
        if m is None:
            raise ValueError(f"書式が不正です: {fmt}")
        percent, decimals, strip = m.group(1) == "%", int(m.group(2)), False
    if percent:
        value = _CONTEXT.multiply(value, Decimal(100))
    q = value.quantize(Decimal(1).scaleb(-decimals), context=_CONTEXT)
    if q.is_zero():
        q = q.copy_abs()  # 「-0」と表示しない
    text = f"{q:,f}"
    if strip and "." in text:
        text = text.rstrip("0").rstrip(".")
        if text == "-0":
            text = "0"
    return text + ("%" if percent else "")


def render(template: str, sources: Mapping[str, SourceValue]) -> str:
    """テンプレートのプレースホルダをすべて数値に置き換える。

    :raises ValueError: 形式の不正なプレースホルダ、または未知の出典 ID があるとき。
    """

    def replace(m: re.Match[str]) -> str:
        p = PLACEHOLDER.fullmatch(m.group(0))
        if p is None:
            raise ValueError(f"プレースホルダの形式が不正です: {m.group(0)}")
        source = sources.get(p.group("source"))
        if source is None:
            raise ValueError(f"未知の出典 ID です: {p.group('source')}")
        return format_value(source.value, p.group("fmt"))

    return BRACKETS.sub(replace, template)
