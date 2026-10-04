"""無職転生のパック（domains/mushoku、ADR-0012）の試験。

- パックの実装をゴールデンケースと照合する（参照実装との照合は tests/test_golden_reference.py）。
- ネタバレ防止：進み具合より先の事実・人物・出来事・道は返さない。見えない項目と存在しない
  項目は同じ誤りにする。正体の別名・タグから、まだ明かされていない関係が漏れないことを、
  資料の規則として確かめる。
- 実物の MCP サーバをゲートウェイから起動し、progress が LLM に見えず、利用者の値で
  絞り込むことを確かめる。
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.evals import load_cases, run_evals
from core.gateway import Budget, Gateway
from domains.mushoku.service import lore

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "domains/mushoku"
DATA = PACK / "data/draft-1"


def _data(name: str) -> dict:
    return yaml.safe_load((DATA / f"{name}.yaml").read_text(encoding="utf-8"))


def _golden() -> list[tuple[str, dict]]:
    cases = []
    for path in sorted((PACK / "golden").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.extend((doc["tool"], c) for c in doc["cases"])
    return cases


def test_every_declared_tool_has_an_implementation_and_golden_cases() -> None:
    manifest = yaml.safe_load((PACK / "domain.yaml").read_text(encoding="utf-8"))
    declared = {t["name"] for t in manifest["tools"]}
    assert declared == set(lore.TOOLS)
    assert {tool for tool, _ in _golden()} == declared
    assert manifest["filter_policy"] == "progress" and manifest["user_context"] == ["progress"]


@pytest.mark.parametrize(
    ("tool", "case"), _golden(), ids=lambda x: x["id"] if isinstance(x, dict) else x
)
def test_pack_implementation_matches_golden(tool: str, case: dict) -> None:
    values = lore.TOOLS[tool](case["input"]).values
    assert values == {k: Decimal(str(v)) for k, v in case["expected"].items()}


# ---------------------------------------------------------------------------
# ネタバレ防止
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "args"),
    [
        (
            lore.age,
            {"person": "ルーデウス", "event": "転移事件", "progress": "novel:2"},
        ),  # 先の出来事
        (lore.age, {"person": "ルーデウス", "event": "存在しない出来事", "progress": "novel:2"}),
        (lore.route, {"from": "ブエナ村", "to": "シャリーア", "progress": "novel:7"}),  # 先の場所
        (lore.route, {"from": "ブエナ村", "to": "存在しない町", "progress": "novel:7"}),
    ],
)
def test_hidden_and_missing_items_give_the_same_error(call, args: dict) -> None:
    with pytest.raises(lore.LoreInputError) as e:
        call(args)
    assert str(e.value).endswith(lore.NOT_FOUND)  # 存在するかどうかを漏らさない


def test_search_never_returns_facts_beyond_the_progress() -> None:
    facts = {f["id"]: f for f in _data("facts")["facts"]}
    for vol in range(1, 27):
        hits = lore.search({"keywords": ["ルーデウス"], "limit": 10, "progress": f"novel:{vol}"})
        assert all(facts[fid]["novel_vol"] <= vol for fid in hits.texts)


def test_no_cross_medium_conversion() -> None:
    # 小説ではずっと先の巻でも、アニメの注記が無い事実はアニメの進み具合では出ない
    late = lore.search({"keywords": ["オルステッド", "ヒトガミ"], "progress": "anime:9-99"})
    assert late.values["count"] == 0
    assert (
        lore.search({"keywords": ["オルステッド", "ヒトガミ"], "progress": "novel:26"}).values[
            "count"
        ]
        > 0
    )


def test_secret_alias_is_not_linked_before_the_reveal() -> None:
    before = lore.search({"keywords": ["フィッツ"], "limit": 10, "progress": "novel:8"})
    assert list(before.texts) == ["fitz_bodyguard"]
    assert not any("シルフィ" in t for t in before.texts.values())
    after = lore.search({"keywords": ["フィッツ"], "limit": 10, "progress": "novel:9"})
    assert "fitz_is_sylphie" in after.texts and "sylphie_friend" in after.texts


@pytest.mark.parametrize(
    ("progress", "message"),
    [
        (None, "progress がありません"),
        ("novel:27", "1〜26"),
        ("anime:2", "<期>-<話>"),
        ("manga:3", "形式"),
    ],
)
def test_progress_is_validated(progress, message: str) -> None:
    with pytest.raises(lore.LoreInputError, match=message):
        lore.search({"keywords": ["ロキシー"], "progress": progress})


def test_data_rules_that_prevent_leaks() -> None:
    """資料の規則：タグの人物・場所は事実より先に登場している／正体の別名は通常の別名に入れない。"""
    entities = {e["id"]: e for e in _data("people")["people"] + _data("places")["places"]}
    for fact in _data("facts")["facts"]:
        assert not re.search(r"[0-9０-９]", fact["text"]), fact["id"]
        for tag in fact["tags"]:
            entity = entities.get(tag)
            if entity is None:
                continue  # 話題のタグ
            assert entity["novel_vol"] <= fact["novel_vol"], (fact["id"], tag)
            if fact["anime_ep"] is not None:
                assert entity["anime_ep"] is not None, (fact["id"], tag)
                assert lore._anime(entity["anime_ep"]) <= lore._anime(fact["anime_ep"]), (
                    fact["id"],
                    tag,
                )
    for person in _data("people")["people"]:
        secret = {a["name"] for a in person.get("secret_aliases", [])}
        assert not secret & set(person.get("aliases", [])), person["id"]
    for item in [*_data("facts")["facts"], *entities.values(), *_data("events")["events"]]:
        assert item["verified"] is False and item["source"].startswith("TODO")  # 未確認の下書き


# ---------------------------------------------------------------------------
# 実物の MCP サーバ
# ---------------------------------------------------------------------------


def _budget(tmp_path: Path) -> Budget:
    return Budget(tmp_path / "costs.jsonl", Decimal(1), Decimal(10))


async def test_gateway_hides_progress_and_filters_with_the_users_value(tmp_path: Path) -> None:
    async with await Gateway.open(
        ROOT, "mushoku", budget=_budget(tmp_path), context={"progress": "novel:1"}
    ) as gw:
        specs = {s.name: s for s in gw.tool_specs()}
        assert set(specs) >= {"lore_search", "timeline_age", "timeline_span", "map_route"}
        assert all("progress" not in s.input_schema.get("properties", {}) for s in specs.values())

        hits = await gw.call("lore_search", {"keywords": ["ロキシー"]})
        assert hits.error is None
        assert set(hits.texts) == {"roxy_tutor", "roxy_migurd"}  # 結婚（12 巻）は出ない
        assert all(s.unverified_inputs for s in hits.sources)

        widened = await gw.call("lore_search", {"keywords": ["ロキシー"], "progress": "novel:26"})
        assert widened.error is not None and "progress" in widened.error

        for case_tool, case in _golden():
            async with await Gateway.open(
                ROOT,
                "mushoku",
                budget=_budget(tmp_path),
                context={"progress": case["input"]["progress"]},
            ) as g:
                args = {k: v for k, v in case["input"].items() if k != "progress"}
                outcome = await g.call(case_tool.replace(".", "_"), args)
                assert outcome.error is None, (case["id"], outcome.error)
                got = {s.source_id.split(".", 1)[1]: s.value for s in outcome.sources}
                assert got == {k: Decimal(str(v)) for k, v in case["expected"].items()}, case["id"]


async def test_without_progress_the_tools_refuse(tmp_path: Path) -> None:
    async with await Gateway.open(ROOT, "mushoku", budget=_budget(tmp_path)) as gw:
        outcome = await gw.call("lore_search", {"keywords": ["ロキシー"]})
        assert outcome.error is not None and "--context progress=" in outcome.error


# ---------------------------------------------------------------------------
# 評価（台本モード）
# ---------------------------------------------------------------------------

SUITES = [
    (ROOT / "evals/faithfulness/mushoku.yaml", ROOT / "evals/reports/scripted-baseline-mushoku.md"),
    (ROOT / "evals/redteam/spoilers.yaml", ROOT / "evals/reports/scripted-baseline-spoilers.md"),
]


@pytest.mark.parametrize(("cases", "baseline"), SUITES, ids=lambda p: p.stem)
async def test_scripted_evals_pass_and_baseline_is_current(
    cases: Path, baseline: Path, tmp_path: Path
) -> None:
    report = await run_evals(llm_kind="scripted", cases_path=cases, raw_dir=tmp_path / "raw")
    assert report.domain == "mushoku"
    assert {r.case_id: r.failures for r in report.results if not r.passed} == {}
    assert report.faithfulness == 1.0 and report.ok
    text = baseline.read_text(encoding="utf-8")
    assert "- ドメイン: `mushoku`" in text
    for case in load_cases(cases):
        assert re.search(rf"\| `{re.escape(case['id'])}` \|.*\| 合格 \|", text), case["id"]
