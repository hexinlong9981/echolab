"""数値トレース検証器とレンダラ（ADR-0005・ADR-0008）。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.contracts import UNVERIFIED_NOTE, SourceValue
from core.verifier import format_value, render, verify


def _src(source_id: str, value: str, unverified: tuple[str, ...] = ()) -> SourceValue:
    return SourceValue(source_id, Decimal(value), "damage.expected", unverified)


SOURCES = {
    s.source_id: s
    for s in (
        _src("c1.total", "6192.000000"),
        _src("c1.base", "5000"),
        _src("c2.total", "6932.5"),
        _src("c3.change", "0.119590", ("gacha_rules:featured",)),
        _src("c3.ratio", "1.119590", ("gacha_rules:featured",)),
        _src("c4.big", "1234567.891"),
        _src("c4.neg", "-1234.5"),
    )
}


# ---------------------------------------------------------------------------
# 書式
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        ("6192.000000", None, "6,192"),
        ("0.615385", None, "0.62"),
        ("1.5", None, "1.5"),
        ("0.125", None, "0.12"),  # ROUND_HALF_EVEN
        ("0.135", None, "0.14"),
        ("0.005", None, "0"),  # 0.00 → 0（末尾の 0 と小数点を落とす）
        ("-0.004", None, "0"),  # -0 と表示しない
        ("1234567.891", None, "1,234,567.89"),
        ("-1234.5", None, "-1,234.5"),
        ("999.999", None, "1,000"),
        ("100", None, "100"),
        ("6192.5", "0", "6,192"),  # 偶数側へ
        ("6193.5", "0", "6,194"),
        ("6192", "1", "6,192.0"),
        ("0.615385", "3", "0.615"),
        ("2.5", "0", "2"),
        ("-0.4", "0", "0"),
        ("0.119590", "%1", "12.0%"),
        ("0.11955", "%2", "11.96%"),
        ("0.6", "%0", "60%"),
        ("0.125", "%0", "12%"),  # 12.5 → 12（偶数側へ）
        ("12.3456", "%0", "1,235%"),
        ("-0.25", "%1", "-25.0%"),
        ("1E+3", None, "1,000"),
    ],
)
def test_format_value(value: str, fmt: str | None, expected: str) -> None:
    assert format_value(Decimal(value), fmt) == expected


@pytest.mark.parametrize("fmt", ["x", "%", "12", "%%1", "-1", ""])
def test_format_value_rejects_bad_format(fmt: str) -> None:
    with pytest.raises(ValueError, match="書式"):
        format_value(Decimal(1), fmt)


def test_render_replaces_placeholders() -> None:
    template = "期待ダメージは [[c1.total]]、強化後は [[c2.total|1]]（[[c3.change|%1]] 増）。"
    assert render(template, SOURCES) == "期待ダメージは 6,192、強化後は 6,932.5（12.0% 増）。"


def test_render_without_placeholders_is_identity() -> None:
    assert render("数値はありません。", SOURCES) == "数値はありません。"


@pytest.mark.parametrize(
    "template", ["[[c9.total]]", "[[c1.total|x]]", "[[c1.Total]]", "[[total]]", "[[c1.total|12]]"]
)
def test_render_rejects_unknown_or_malformed(template: str) -> None:
    with pytest.raises(ValueError):
        render(template, SOURCES)


# ---------------------------------------------------------------------------
# 検証：受理
# ---------------------------------------------------------------------------


def test_accepts_template_with_only_placeholders() -> None:
    v = verify("期待ダメージは [[c1.total|0]] です。基礎は [[c1.base]]。", "期待値は？", SOURCES)
    assert v.ok, v.problems
    assert v.problems == ()
    assert v.rendered == "期待ダメージは 6,192 です。基礎は 5,000。"
    assert v.cited == ("c1.total", "c1.base")


def test_accepts_text_without_numbers() -> None:
    v = verify("ツールが使えないため、数値ではお答えできません。", "攻撃力は？", {})
    assert v.ok
    assert v.rendered == "ツールが使えないため、数値ではお答えできません。"
    assert v.cited == ()


def test_cited_is_in_order_without_duplicates() -> None:
    v = verify("[[c2.total]] と [[c1.total]]、再掲 [[c2.total|0]]", "", SOURCES)
    assert v.cited == ("c2.total", "c1.total")


@pytest.mark.parametrize(
    ("template", "question"),
    [
        ("攻撃力 2000 の場合、[[c1.total]] です。", "攻撃力2000、会心率60%のときの期待値は？"),
        ("攻撃力 2,000 の場合", "攻撃力2000では？"),  # 桁区切り
        ("攻撃力 2000 の場合", "攻撃力2,000では？"),
        ("会心率 60% のとき", "会心率0.6のとき"),  # パーセント ↔ 小数
        ("会心率 0.6 のとき", "会心率60%のとき"),
        ("会心率 60 % ではなく 60% のとき", "会心率60％のとき"),  # 全角の％
        ("攻撃力 ２０００ の場合", "攻撃力2000では？"),  # 全角数字（回答側）
        ("攻撃力 2000 の場合", "攻撃力２，０００では？"),  # 全角数字・全角カンマ（質問側）
        ("耐性 10.0% のとき", "耐性10%"),  # 小数点以下の 0
        ("80 回以内に引ける確率は [[c3.ratio|%1]]", "80回以内に引ける確率は？"),
    ],
)
def test_accepts_numbers_quoted_from_question(template: str, question: str) -> None:
    v = verify(template, question, SOURCES)
    assert v.ok, v.problems


@pytest.mark.parametrize(
    "template",
    [
        "1. 会心率を上げる\n2. 攻撃力を上げる",
        "1) 一つ目\n2) 二つ目",
        "（1）一つ目\n（2）二つ目",
        "３．全角の番号\n４．続き",
        "  10. 字下げした番号",
        "方法は 3 つあります。",
        "3つの方法",
        "方法有 3 种。",
        "分 2 步计算",
        "There are 2 points:",
        "in 3 steps",
        "評価は 10点",
        "2 種類のサブ詞条",
        "1位は会心率、2番目は攻撃力",
        "１位は会心率",
    ],
)
def test_accepts_allowlisted_numbers(template: str) -> None:
    v = verify(template, "どうすればいい？", {})
    assert v.ok, v.problems


# ---------------------------------------------------------------------------
# 検証：差し戻し
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("template", "number"),
    [
        ("期待ダメージは 6192 です。", "6192"),  # 書き写し
        ("期待ダメージは 6,192 です。", "6,192"),
        ("差は約 740 です。", "740"),  # 自分で計算した派生値
        ("[[c1.total]] は [[c2.total]] より 12% 低い", "12%"),
        ("期待ダメージは ６１９２ です。", "6192"),  # 全角数字
        ("1.5倍になります", "1.5"),  # 行頭でも小数は番号ではない
        ("方法は 11 つあります", "11"),  # 許可は 10 以下
        ("about 2 damage", "2"),  # 英語は決めた名詞が直後に続くときだけ許す
        ("2 key points", "2"),  # 間に別の語が入ると許さない
        ("2.5つ", "2.5"),
        ("3 回引く", "3"),  # 許可リストに無い助数詞
        ("文中の 1. は番号ではない", "1"),
    ],
)
def test_rejects_unsourced_numbers(template: str, number: str) -> None:
    v = verify(template, "攻撃力2000の期待値は？", SOURCES)
    assert not v.ok
    assert v.rendered is None
    assert any(f"「{number}」" in p for p in v.problems), v.problems


def test_percent_equivalence_is_value_based_not_textual() -> None:
    # 質問の 60 と回答の 0.6 は等しくない（％ が付いていない）
    assert not verify("0.6 です", "60では？", {}).ok
    assert verify("60% です", "60では？", {}).ok


def test_rejects_unknown_source_id() -> None:
    v = verify("期待ダメージは [[c9.total]] です。", "", SOURCES)
    assert not v.ok
    assert any("c9.total" in p for p in v.problems)


@pytest.mark.parametrize(
    "template", ["[[c1.total|x]]", "[[c1.total|12]]", "[[ c1.total ]]", "[[c1.TOTAL]]"]
)
def test_rejects_malformed_placeholder(template: str) -> None:
    v = verify(f"期待ダメージは {template} です。", "", SOURCES)
    assert not v.ok
    assert any("形式が不正" in p for p in v.problems), v.problems


def test_reports_every_problem() -> None:
    v = verify("[[c9.x]] と 6192 と 740", "", SOURCES)
    assert len(v.problems) == 3


# ---------------------------------------------------------------------------
# 未確認データの注記（ADR-0006）
# ---------------------------------------------------------------------------


def test_note_added_when_citing_unverified_source() -> None:
    v = verify("確率は [[c3.ratio|%1]] です。", "", SOURCES)
    assert v.ok
    assert v.rendered == "確率は 112.0% です。\n\n" + UNVERIFIED_NOTE


def test_no_note_when_unverified_source_not_cited() -> None:
    v = verify("期待ダメージは [[c1.total]] です。", "", SOURCES)
    assert v.ok
    assert v.rendered is not None
    assert UNVERIFIED_NOTE not in v.rendered
