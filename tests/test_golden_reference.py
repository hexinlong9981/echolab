"""ゴールデンケースの期待値を Python の参照実装で再計算する（言語をまたいだ契約テスト）。

Java（services/calc-engine の GoldenContractTest）も同じ YAML を検査するので、
YAML・Java・Python の 3 者が一致していることになる。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from tests.reference import calc_reference as ref

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "domains/wuwa/golden"

CALCULATORS: dict[str, Callable[[dict], dict[str, float]]] = {
    "damage.expected": lambda i: {k: float(v) for k, v in ref.damage_expected(i).items()},
    "echo.score": lambda i: {k: float(v) for k, v in ref.echo_score(i).items()},
    "gacha.probability_within": lambda i: {"probability": ref.gacha_probability_within(i)},
}


def _cases() -> list[tuple[str, dict]]:
    cases = []
    for path in sorted(GOLDEN_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.extend((doc["tool"], c) for c in doc["cases"])
    return cases


def test_every_tool_has_a_reference() -> None:
    assert {tool for tool, _ in _cases()} == set(CALCULATORS)


def _case_id(x: object) -> str:
    return x["id"] if isinstance(x, dict) else str(x)


@pytest.mark.parametrize(("tool", "case"), _cases(), ids=_case_id)
def test_reference_matches_golden(tool: str, case: dict) -> None:
    actual = CALCULATORS[tool](case["input"])
    assert set(actual) == set(case["expected"])
    for field, expected in case["expected"].items():
        assert actual[field] == pytest.approx(expected, abs=case["tolerance"]), (case["id"], field)
