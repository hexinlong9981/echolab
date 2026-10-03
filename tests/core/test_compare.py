"""比較ツールの計算（ADR-0005）。ゴールデンケースは tests/test_golden_reference.py で照合する。"""

from __future__ import annotations

from decimal import Decimal as D

import pytest
from jsonschema import Draft202012Validator

from core.compare import COMPARE_SPECS, COMPARE_TOOLS, diff, ratio
from core.contracts import ToolError, to_wire_name


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("6932.5", "6192", "740.500000"),
        ("1", "1.5", "-0.500000"),
        ("0.1", "0.1", "0.000000"),
        ("1.0000005", "1", "0.000000"),  # 偶数側へ
        ("1.0000015", "1", "0.000002"),
        ("1.0000025", "1", "0.000002"),
        ("-1.0000005", "-1", "0.000000"),  # -0 にしない
        ("123456789012.5", "0", "123456789012.500000"),  # 有効桁 16 を超える桁数でも丸められる
    ],
)
def test_diff(a: str, b: str, expected: str) -> None:
    result = diff(D(a), D(b))
    assert set(result) == {"diff"}
    assert str(result["diff"]) == expected


@pytest.mark.parametrize(
    ("a", "b", "r", "change"),
    [
        ("7740", "6192", "1.250000", "0.250000"),
        ("3", "4", "0.750000", "-0.250000"),
        ("2", "3", "0.666667", "-0.333333"),
        ("1", "3", "0.333333", "-0.666667"),
        ("-1", "-4", "0.250000", "-0.750000"),
        ("0", "7", "0.000000", "-1.000000"),
        ("1", "8000000", "0.000000", "-1.000000"),  # 0.000000125 → 偶数側の 0.000000
        ("3", "8000000", "0.000000", "-1.000000"),  # 0.000000375 → 0.000000
        ("5", "8000000", "0.000001", "-0.999999"),  # 0.000000625 → 0.000001
    ],
)
def test_ratio(a: str, b: str, r: str, change: str) -> None:
    result = ratio(D(a), D(b))
    assert {k: str(v) for k, v in result.items()} == {"ratio": r, "change": change}


def test_ratio_uses_16_significant_digits_before_rounding() -> None:
    # 1/3 を 16 桁で計算してから 1 を引く（0.3333333333333333 − 1）
    assert ratio(D(1), D(3))["change"] == D("-0.666667")


def test_ratio_by_zero_is_tool_error() -> None:
    with pytest.raises(ToolError, match="b が 0"):
        ratio(D(1), D(0))
    with pytest.raises(ToolError):
        ratio(D(0), D("0.000"))


def test_specs_match_tools() -> None:
    assert [s.name for s in COMPARE_SPECS] == [to_wire_name(t) for t in COMPARE_TOOLS]
    assert [s.name for s in COMPARE_SPECS] == ["compare_diff", "compare_ratio"]
    for spec in COMPARE_SPECS:
        assert "出典 ID" in spec.description
        Draft202012Validator.check_schema(dict(spec.input_schema))
        v = Draft202012Validator(dict(spec.input_schema))
        assert v.is_valid({"a": "c1.total", "b": "c12.base_value"})
        assert not v.is_valid({"a": 1, "b": "c1.total"})
        assert not v.is_valid({"a": "total", "b": "c1.total"})
        assert not v.is_valid({"a": "c1.total"})
