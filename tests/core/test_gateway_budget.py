"""コストの台帳と上限（ADR-0008）。時刻は差し替えた時計で試す。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from core.contracts import BudgetExceeded
from core.gateway import Budget, BudgetConfigError, ModelPrice

MODEL = "claude-opus-5-5"
ROOT = Path(__file__).resolve().parents[2]
JST = timezone(timedelta(hours=9))


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _budget(tmp_path: Path, clock: Clock, daily: str = "1.00", monthly: str = "10.00") -> Budget:
    return Budget(tmp_path / "ledger/costs.jsonl", Decimal(daily), Decimal(monthly), clock)


def _usd(n: str) -> dict[str, int]:
    """出力トークンだけで ``n`` USD になる使用量（出力 20 USD / 100 万トークン）。"""
    return {"output_tokens": int(Decimal(n) * 50_000)}


def test_cost_uses_pricing_table(tmp_path: Path) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
    }
    assert b.cost(MODEL, usage) == Decimal("29.20")  # 4 + 20 + 5 + 0.2
    assert b.cost(MODEL, {"input_tokens": 1234, "output_tokens": 567}) == Decimal("0.016276")
    assert b.cost(MODEL, {}) == 0
    # cache_write は入力の 1.25 倍（5 分 TTL）
    p = b.pricing[MODEL]
    assert p.cache_write == p.input * Decimal("1.25")
    assert isinstance(b.cost(MODEL, usage), Decimal)


def test_unknown_model_cost_is_refused(tmp_path: Path) -> None:
    """cost() は料金を推測しない（record() は課金済みのため最高料金で見積もる。下の試験）。"""
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    with pytest.raises(ValueError, match="料金表に無いモデル"):
        b.cost("claude-unknown-9", {"input_tokens": 1})
    assert not b.ledger_path.exists()


def test_negative_tokens_are_refused(tmp_path: Path) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    with pytest.raises(ValueError):
        b.cost(MODEL, {"input_tokens": -1})


def test_record_appends_ledger(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    b = _budget(tmp_path, clock)
    assert b.record(MODEL, {"input_tokens": 1000, "output_tokens": 100, "extra": 5}) == Decimal(
        "0.006"
    )
    b.record(MODEL, {"cache_read_input_tokens": 1000})
    lines = b.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first == {
        "ts": "2026-10-03T12:00:00+00:00",
        "model": MODEL,
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "usd": "0.006",
    }
    assert b.spent_today() == Decimal("0.0062")
    assert b.spent_month() == Decimal("0.0062")


def test_no_ledger_means_nothing_spent(tmp_path: Path) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    assert b.spent_today() == 0
    assert b.spent_month() == 0
    b.check()


def test_daily_cap(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 10, 3, 1, 0, tzinfo=UTC))
    b = _budget(tmp_path, clock)
    b.record(MODEL, _usd("0.99"))
    b.check()  # 上限未満
    b.record(MODEL, _usd("0.01"))
    with pytest.raises(BudgetExceeded, match="今日"):
        b.check()  # ちょうど上限で止める
    # UTC の翌日になれば呼べる
    clock.now = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
    assert b.spent_today() == 0
    b.check()


def test_day_boundary_is_utc_not_local(tmp_path: Path) -> None:
    # 日本時間 10/4 08:59 は UTC では 10/3 23:59：まだ「今日」
    clock = Clock(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    b = _budget(tmp_path, clock)
    b.record(MODEL, _usd("1"))
    clock.now = datetime(2026, 10, 4, 8, 59, tzinfo=JST)
    with pytest.raises(BudgetExceeded):
        b.check()
    clock.now = datetime(2026, 10, 4, 9, 0, tzinfo=JST)
    b.check()


def test_monthly_cap_and_month_boundary(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    b = _budget(tmp_path, clock, daily="5", monthly="10")
    for day in range(1, 4):
        clock.now = datetime(2026, 10, day, 6, tzinfo=UTC)
        b.record(MODEL, _usd("3.5"))
    assert b.spent_month() == Decimal("10.5")
    assert b.spent_today() == Decimal("3.5")
    with pytest.raises(BudgetExceeded, match="今月"):
        b.check()
    clock.now = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)
    with pytest.raises(BudgetExceeded):
        b.check()
    clock.now = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
    assert b.spent_month() == 0
    b.check()


def test_same_month_other_year_is_not_counted(tmp_path: Path) -> None:
    clock = Clock(datetime(2025, 10, 3, tzinfo=UTC))
    b = _budget(tmp_path, clock)
    b.record(MODEL, _usd("50"))
    clock.now = datetime(2026, 10, 3, tzinfo=UTC)
    assert b.spent_today() == 0
    assert b.spent_month() == 0


def test_naive_clock_is_rejected(tmp_path: Path) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3)))
    with pytest.raises(ValueError, match="タイムゾーン"):
        b.record(MODEL, {"input_tokens": 1})


def test_broken_ledger_fails_closed(tmp_path: Path) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    b.ledger_path.parent.mkdir(parents=True)
    b.ledger_path.write_text('{"ts": "2026-10-03T00:00:00+00:00"\n', encoding="utf-8")
    with pytest.raises(BudgetConfigError, match="1 行目") as info:
        b.check()
    assert str(b.ledger_path) in str(info.value)
    assert "安全に判定できません" in str(info.value)


@pytest.mark.parametrize("line", ['{"ts": "2026-10-03T00:00:00+00:00", "usd": null}', "[]"])
def test_ledger_with_wrong_types_fails_closed(tmp_path: Path, line: str) -> None:
    b = _budget(tmp_path, Clock(datetime(2026, 10, 3, tzinfo=UTC)))
    b.ledger_path.parent.mkdir(parents=True)
    b.ledger_path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(BudgetConfigError, match="1 行目"):
        b.check()


@pytest.mark.parametrize("name", ["ECHOLAB_DAILY_USD", "ECHOLAB_MONTHLY_USD"])
@pytest.mark.parametrize("value", ["abc", "-1", "NaN", ""])
def test_invalid_cap_in_environment_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(BudgetConfigError, match=f"環境変数 {name} の値「{value}」"):
        Budget.from_config(ROOT)


def test_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ECHOLAB_DAILY_USD", "ECHOLAB_MONTHLY_USD", "ECHOLAB_LEDGER"):
        monkeypatch.delenv(name, raising=False)
    b = Budget.from_config(ROOT)
    assert b.daily_usd == Decimal("1.00")
    assert b.monthly_usd == Decimal("10.00")
    assert b.ledger_path == ROOT / ".echolab/costs.jsonl"
    assert b.pricing[MODEL] == ModelPrice(
        input=Decimal("4.00"),
        output=Decimal("20.00"),
        cache_read=Decimal("0.20"),
        cache_write=Decimal("5.00"),
    )


def test_from_config_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ECHOLAB_DAILY_USD", "0.5")
    monkeypatch.setenv("ECHOLAB_MONTHLY_USD", "2")
    monkeypatch.setenv("ECHOLAB_LEDGER", str(tmp_path / "x.jsonl"))
    b = Budget.from_config(ROOT)
    assert (b.daily_usd, b.monthly_usd) == (Decimal("0.5"), Decimal(2))
    assert b.ledger_path == tmp_path / "x.jsonl"
    monkeypatch.setenv("ECHOLAB_LEDGER", "tmp/y.jsonl")
    assert Budget.from_config(ROOT).ledger_path == ROOT / "tmp/y.jsonl"


def test_default_pricing_is_loaded_from_config(tmp_path: Path) -> None:
    b = Budget(tmp_path / "c.jsonl", Decimal(1), Decimal(10))
    assert MODEL in b.pricing


def test_record_unknown_model_is_estimated_at_highest_price(tmp_path: Path) -> None:
    """課金済みの呼び出しは、料金表に無いモデルでも失敗させず、最高料金で見積もって記録する。"""
    pricing = {
        "cheap": ModelPrice(Decimal("1"), Decimal("1"), Decimal("0"), Decimal("0")),
        "pricey": ModelPrice(Decimal("10"), Decimal("50"), Decimal("0"), Decimal("0")),
    }
    budget = Budget(tmp_path / "l.jsonl", Decimal("100"), Decimal("100"), pricing=pricing)
    usd = budget.record("unknown-model", {"input_tokens": 1_000_000, "output_tokens": 0})
    assert usd == Decimal("10")
    entry = json.loads((tmp_path / "l.jsonl").read_text(encoding="utf-8"))
    assert entry["estimated"] is True
    assert budget.spent_today() == Decimal("10")
