"""ゲートウェイ：許可リスト・入力の検査・採番・比較ツールの解決（ADR-0008）。"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.contracts import ToolEnvelope, ToolSpec
from core.gateway import Budget, Gateway
from tests.core.fakes import FakeCalcBackend

ROOT = Path(__file__).resolve().parents[2]
DAMAGE = yaml.safe_load((ROOT / "domains/wuwa/golden/damage.yaml").read_text(encoding="utf-8"))
DMG_1 = DAMAGE["cases"][0]["input"]  # total = 6192
DMG_2 = DAMAGE["cases"][1]["input"]
ECHO = yaml.safe_load((ROOT / "domains/wuwa/golden/echo_score.yaml").read_text(encoding="utf-8"))
ECHO_1 = ECHO["cases"][0]["input"]


@pytest.fixture
def budget(tmp_path: Path) -> Budget:
    return Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))


@pytest.fixture
async def fake() -> FakeCalcBackend:
    return FakeCalcBackend(unverified={"echo.score": ("echo_weights:sample",)})


@pytest.fixture
async def gw(fake: FakeCalcBackend, budget: Budget):
    gateway = await Gateway.open(
        ROOT, "wuwa", backends={"calc-engine": fake, "vision-mcp": FakeCalcBackend()}, budget=budget
    )
    async with gateway:
        yield gateway


class ExtraToolsBackend(FakeCalcBackend):
    """宣言の無いツールと、厳しい入力スキーマを持つツールを公開する偽物。"""

    async def list_tools(self) -> list[ToolSpec]:
        specs = [s for s in await super().list_tools() if s.name != "damage_expected"]
        strict = {
            "type": "object",
            "properties": {"atk": {"type": "number", "minimum": 0}},
            "required": ["atk"],
        }
        return [
            *specs,
            ToolSpec("damage_expected", "", strict),
            ToolSpec("admin_reset", "宣言されていない危険なツール", {"type": "object"}),
        ]


# ---------------------------------------------------------------------------
# 許可リスト
# ---------------------------------------------------------------------------


async def test_tool_specs_are_declared_and_exposed_tools_plus_compare(gw: Gateway) -> None:
    names = [s.name for s in gw.tool_specs()]
    # gacha.simulate は宣言されているが、偽物のサービスが公開していないので見せない
    assert names == [
        "damage_expected",
        "echo_score",
        "gacha_probability_within",
        "echo_read_screenshot",  # vision-mcp のツール
        "compare_diff",
        "compare_ratio",
    ]


async def test_undeclared_tool_is_hidden_and_refused(budget: Budget) -> None:
    backend = ExtraToolsBackend()
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": backend, "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        assert "admin_reset" not in {s.name for s in gw.tool_specs()}
        out = await gw.call("admin_reset", {})
        assert out.error is not None
        assert "許可されていません" in out.error
        assert backend.calls == []


async def test_unknown_and_declared_but_unexposed_tools_are_refused(
    gw: Gateway, fake: FakeCalcBackend
) -> None:
    for name in ("no_such_tool", "gacha_simulate", "damage.expected"):
        out = await gw.call(name, {})
        assert out.error is not None
        assert out.sources == ()
    assert fake.calls == []


async def test_empty_backend_description_falls_back_to_domain(budget: Budget) -> None:
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": ExtraToolsBackend(), "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        spec = next(s for s in gw.tool_specs() if s.name == "damage_expected")
        assert spec.description == "期待ダメージと各乗区の明細"


async def test_unknown_domain_is_rejected(budget: Budget) -> None:
    with pytest.raises(ValueError, match="ドメインが見つかりません"):
        await Gateway.open(ROOT, "no_such_domain", backends={}, budget=budget)


async def test_aclose_closes_backends(fake: FakeCalcBackend, budget: Budget) -> None:
    gw = await Gateway.open(
        ROOT, "wuwa", backends={"calc-engine": fake, "vision-mcp": FakeCalcBackend()}, budget=budget
    )
    await gw.aclose()
    await gw.aclose()
    assert fake.closed
    assert (await gw.call("damage_expected", DMG_1)).error == "ゲートウェイは閉じています"


async def test_open_uses_budget_from_config_by_default(fake: FakeCalcBackend) -> None:
    async with await Gateway.open(
        ROOT, "wuwa", backends={"calc-engine": fake, "vision-mcp": FakeCalcBackend()}
    ) as gw:
        assert gw.budget.daily_usd == Decimal("1.00")


# ---------------------------------------------------------------------------
# 入力の検査
# ---------------------------------------------------------------------------


async def test_schema_violation_is_error_and_backend_not_called(budget: Budget) -> None:
    backend = ExtraToolsBackend()
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": backend, "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        for bad in ({}, {"atk": "2000"}, {"atk": -1}):
            out = await gw.call("damage_expected", bad)
            assert out.error is not None
            assert out.error.startswith("入力が不正です")
        assert backend.calls == []
        assert gw.sources == {}


class SchemaMessagesBackend(FakeCalcBackend):
    """よく使う検査（必須・型・範囲・列挙・余分な項目・形式）を持つスキーマのツール。"""

    async def list_tools(self) -> list[ToolSpec]:
        schema = {
            "type": "object",
            "properties": {
                "pulls": {"type": "integer", "minimum": 1, "maximum": 10000},
                "mode": {"enum": ["fast", "exact"]},
                "banner": {"type": "string", "pattern": "^[a-z_]+$"},
                "rules": {
                    "type": "object",
                    "properties": {"rate": {"type": "number", "exclusiveMinimum": 0}},
                },
            },
            "required": ["pulls"],
            "additionalProperties": False,
        }
        return [ToolSpec("gacha_probability_within", "", schema)]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, "(全体): 必須の項目がありません: pulls"),
        ({"pulls": "10"}, 'pulls: "10" は整数ではありません'),
        ({"pulls": 20000}, "pulls: 20000 は最大値 10000 より大きい値です"),
        ({"pulls": 0}, "pulls: 0 は最小値 1 より小さい値です"),
        (
            {"pulls": 1, "mode": "slow"},
            'mode: "slow" は使えない値です（使える値: "fast", "exact"）',
        ),
        ({"pulls": 1, "extra": 1}, "(全体): 使えない項目があります: extra"),
        ({"pulls": 1, "banner": "A-1"}, 'banner: "A-1" は形式（^[a-z_]+$）に合いません'),
        ({"pulls": 1, "rules": {"rate": 0}}, "rules/rate: 0 は 0 より大きい値である必要があります"),
    ],
)
async def test_schema_errors_are_explained_in_japanese(
    budget: Budget, args: dict[str, Any], expected: str
) -> None:
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": SchemaMessagesBackend(), "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        out = await gw.call("gacha_probability_within", args)
    assert out.error == f"入力が不正です: {expected}"


async def test_tool_error_becomes_error_outcome(gw: Gateway) -> None:
    out = await gw.call("damage_expected", {"atk": 1})  # 必要な項目が足りない
    assert out.error is not None
    assert "入力が不正です" in out.error
    assert out.for_llm() == {"call_id": "c1", "error": out.error}


class WrongNameBackend(FakeCalcBackend):
    async def call_tool(self, wire_name: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        return ToolEnvelope(tool="echo.score", values={"Bad-Field": Decimal(1)})


async def test_mismatched_envelope_is_error(budget: Budget) -> None:
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": WrongNameBackend(), "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        out = await gw.call("damage_expected", DMG_1)
        assert out.error is not None
        assert "一致しません" in out.error
        out = await gw.call("echo_score", {})
        assert out.error is not None
        assert "フィールド名" in out.error
        assert gw.sources == {}


# ---------------------------------------------------------------------------
# 採番
# ---------------------------------------------------------------------------


async def test_call_and_source_ids(gw: Gateway) -> None:
    first = await gw.call("damage_expected", DMG_1)
    assert first.error is None
    assert first.call_id == "c1"
    assert first.tool == "damage.expected"
    assert first.arguments == DMG_1
    ids = [s.source_id for s in first.sources]
    assert "c1.total" in ids
    assert all(i.startswith("c1.") for i in ids)
    total = gw.sources["c1.total"]
    assert total.value == Decimal("6192")
    assert total.tool == "damage.expected"
    assert total.unverified_inputs == ()

    # 失敗した呼び出しも ID を消費する
    assert (await gw.call("no_such_tool", {})).call_id == "c2"
    second = await gw.call("damage_expected", DMG_2)
    assert second.call_id == "c3"
    assert "c3.total" in gw.sources
    assert set(gw.sources) == {s.source_id for s in (*first.sources, *second.sources)}


async def test_concurrent_calls_get_unique_ids(gw: Gateway) -> None:
    outs = await asyncio.gather(*(gw.call("damage_expected", DMG_1) for _ in range(20)))
    assert sorted(o.call_id for o in outs) == sorted(f"c{n}" for n in range(1, 21))
    assert len({f"{o.call_id}.total" for o in outs} & set(gw.sources)) == 20


async def test_unverified_inputs_carried_to_sources(gw: Gateway) -> None:
    out = await gw.call("echo_score", ECHO_1)
    assert out.error is None, out.error
    assert all(s.unverified_inputs == ("echo_weights:sample",) for s in out.sources)
    assert out.for_llm()["unverified"] == ["echo_weights:sample"]


async def test_sources_view_is_read_only_copy(gw: Gateway) -> None:
    await gw.call("damage_expected", DMG_1)
    view = gw.sources
    assert isinstance(view, Mapping)
    dict(view).clear()
    assert "c1.total" in gw.sources


# ---------------------------------------------------------------------------
# 比較ツール
# ---------------------------------------------------------------------------


async def test_compare_resolves_source_ids(gw: Gateway, fake: FakeCalcBackend) -> None:
    a = await gw.call("damage_expected", DMG_2)
    b = await gw.call("damage_expected", DMG_1)
    total_a = gw.sources["c1.total"].value
    calls_before = len(fake.calls)

    d = await gw.call("compare_diff", {"a": "c1.total", "b": "c2.total"})
    assert d.error is None
    assert d.tool == "compare.diff"
    assert d.call_id == "c3"
    assert d.arguments == {"a": "c1.total", "b": "c2.total"}
    assert gw.sources["c3.diff"].value == (total_a - Decimal(6192)).quantize(Decimal("0.000001"))

    r = await gw.call("compare_ratio", {"a": "c2.total", "b": "c2.base"})
    assert r.error is None
    assert gw.sources["c4.ratio"].value == Decimal("1.238400")
    assert gw.sources["c4.change"].value == Decimal("0.238400")
    assert gw.sources["c4.ratio"].tool == "compare.ratio"
    # 比較の結果もさらに比較できる
    rr = await gw.call("compare_diff", {"a": "c4.ratio", "b": "c4.change"})
    assert gw.sources[f"{rr.call_id}.diff"].value == Decimal(1)
    # 比較ツールはサービスを呼ばない
    assert len(fake.calls) == calls_before
    assert a.error is None
    assert b.error is None


async def test_compare_unknown_source_is_error(gw: Gateway) -> None:
    await gw.call("damage_expected", DMG_1)
    out = await gw.call("compare_diff", {"a": "c1.total", "b": "c9.total"})
    assert out.error is not None
    assert "c9.total" in out.error
    assert out.sources == ()


async def test_compare_rejects_numbers_and_bad_ids(gw: Gateway) -> None:
    await gw.call("damage_expected", DMG_1)
    for bad in (
        {"a": 6192, "b": "c1.total"},
        {"a": "6192", "b": "c1.total"},
        {"a": "c1.total"},
        {"a": "c1.total", "b": "c1.total", "c": "c1.total"},
    ):
        out = await gw.call("compare_ratio", bad)
        assert out.error is not None
        assert out.error.startswith("入力が不正です"), bad


async def test_compare_ratio_by_zero_is_error(gw: Gateway) -> None:
    await gw.call("damage_expected", DMG_1)
    await gw.call("damage_expected", DMG_1)
    d = await gw.call("compare_diff", {"a": "c1.total", "b": "c2.total"})
    out = await gw.call("compare_ratio", {"a": "c1.total", "b": f"{d.call_id}.diff"})
    assert out.error is not None
    assert "0" in out.error


async def test_compare_propagates_union_of_unverified(budget: Budget) -> None:
    fake = FakeCalcBackend(
        unverified={
            "echo.score": ("echo_weights:a", "shared:x"),
            "damage.expected": ("shared:x", "dmg:b"),
        }
    )
    async with await Gateway.open(
        ROOT, "wuwa", backends={"calc-engine": fake, "vision-mcp": FakeCalcBackend()}, budget=budget
    ) as gw:
        await gw.call("echo_score", ECHO_1)
        await gw.call("damage_expected", DMG_1)
        out = await gw.call("compare_ratio", {"a": "c1.score", "b": "c2.total"})
        assert out.error is None, out.error
        for s in out.sources:
            assert s.unverified_inputs == ("echo_weights:a", "shared:x", "dmg:b")


async def test_compare_of_verified_values_has_no_unverified(gw: Gateway) -> None:
    await gw.call("damage_expected", DMG_1)
    out = await gw.call("compare_diff", {"a": "c1.total", "b": "c1.base"})
    assert out.for_llm()["unverified"] == []


async def test_domain_may_not_declare_compare_tools(tmp_path: Path, budget: Budget) -> None:
    (tmp_path / "domains/bad").mkdir(parents=True)
    (tmp_path / "domains/bad/domain.yaml").write_text(
        yaml.safe_dump(
            {"name": "bad", "tools": [{"name": "compare.diff", "service": "x"}]},
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="比較ツール"):
        await Gateway.open(tmp_path, "bad", backends={}, budget=budget)
