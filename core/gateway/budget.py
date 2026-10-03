"""LLM のコストの記録と上限（ADR-0008）。

- 呼び出しごとの使用量と金額を JSONL の台帳（既定 ``.echolab/costs.jsonl``）に追記する。
- 今日または今月の合計が上限以上なら :class:`~core.contracts.BudgetExceeded` を送出する。
- 「今日」「今月」は UTC で区切る（日本時間では毎日 9:00 に日付が変わる）。
- 金額はすべて :class:`~decimal.Decimal` で扱う。料金表に無いモデルは推測せずに拒否する。
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from core.contracts import BudgetExceeded

CONFIG_PATH = Path("config/budget.yaml")
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: 使用量のキー → 料金表のキー。
USAGE_KEYS: Mapping[str, str] = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_creation_input_tokens": "cache_write",
    "cache_read_input_tokens": "cache_read",
}
_MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelPrice:
    """100 万トークンあたりの USD。``cache_write`` は 5 分 TTL のキャッシュ書き込み。"""

    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal

    @staticmethod
    def from_mapping(doc: Mapping[str, object]) -> ModelPrice:
        return ModelPrice(**{k: Decimal(str(doc[k])) for k in USAGE_KEYS.values()})


class BudgetConfigError(ValueError):
    """上限の設定（環境変数・``config/budget.yaml``）か台帳が不正で、上限を安全に判定できない。"""


def _load_config(repo_root: Path) -> dict:
    return yaml.safe_load((repo_root / CONFIG_PATH).read_text(encoding="utf-8"))


def load_pricing(repo_root: Path = _REPO_ROOT) -> dict[str, ModelPrice]:
    """``config/budget.yaml`` の料金表を読む。"""
    table = _load_config(repo_root)["pricing_usd_per_mtok"]
    return {model: ModelPrice.from_mapping(p) for model, p in table.items()}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Budget:
    """コストの台帳と、日次・月次の上限。"""

    def __init__(
        self,
        ledger_path: Path,
        daily_usd: Decimal,
        monthly_usd: Decimal,
        clock: Callable[[], datetime] = _utc_now,
        *,
        pricing: Mapping[str, ModelPrice] | None = None,
    ) -> None:
        """
        :param clock: タイムゾーン付きの現在時刻を返す関数（試験で差し替える）。
        :param pricing: モデル名 → 料金。省略時は ``config/budget.yaml`` の料金表。
        """
        self.ledger_path = Path(ledger_path)
        self.daily_usd = Decimal(daily_usd)
        self.monthly_usd = Decimal(monthly_usd)
        self.clock = clock
        self.pricing = dict(pricing) if pricing is not None else load_pricing()

    @classmethod
    def from_config(cls, repo_root: Path) -> Budget:
        """``config/budget.yaml`` から作る。環境変数があれば上書きする。

        - ``ECHOLAB_DAILY_USD``・``ECHOLAB_MONTHLY_USD``：上限（USD）
        - ``ECHOLAB_LEDGER``：台帳のパス（相対パスはリポジトリ直下から）
        """
        config = _load_config(repo_root)
        daily = _usd_setting("ECHOLAB_DAILY_USD", "caps_usd.daily", config["caps_usd"]["daily"])
        monthly = _usd_setting(
            "ECHOLAB_MONTHLY_USD", "caps_usd.monthly", config["caps_usd"]["monthly"]
        )
        ledger = Path(os.environ.get("ECHOLAB_LEDGER", config["ledger"]))
        if not ledger.is_absolute():
            ledger = repo_root / ledger
        pricing = {
            model: ModelPrice.from_mapping(p) for model, p in config["pricing_usd_per_mtok"].items()
        }
        return cls(ledger, daily, monthly, pricing=pricing)

    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("clock はタイムゾーン付きの時刻を返してください")
        return now.astimezone(UTC)

    def cost(self, model: str, usage: Mapping[str, int]) -> Decimal:
        """使用量の金額（USD）。

        :raises ValueError: 料金表に無いモデルのとき（推測しない）。
        """
        price = self.pricing.get(model)
        if price is None:
            raise ValueError(
                f"料金表に無いモデルです（config/budget.yaml に追加してください）: {model}"
            )
        total = Decimal(0)
        for usage_key, price_key in USAGE_KEYS.items():
            tokens = int(usage.get(usage_key) or 0)
            if tokens < 0:
                raise ValueError(f"トークン数が負です: {usage_key}={tokens}")
            total += Decimal(tokens) * getattr(price, price_key)
        return total / _MILLION

    def record(self, model: str, usage: Mapping[str, int]) -> Decimal:
        """1 回の LLM 呼び出しの使用量を台帳に追記し、その金額（USD）を返す。

        呼び出しはすでに課金済みなので、料金表に無いモデル（拒否時のフォールバック先など）でも
        失敗させずに記録する。その場合は料金表で最も高い料金で見積もり、``estimated`` を付ける
        （上限の判定が甘くならないよう、安全側に倒す）。
        """
        estimated = model not in self.pricing
        usd = self._conservative_cost(usage) if estimated else self.cost(model, usage)
        entry = {
            "ts": self._now().isoformat(),
            "model": model,
            "usage": {k: int(usage.get(k) or 0) for k in USAGE_KEYS},
            "usd": str(usd),
        }
        if estimated:
            entry["estimated"] = True
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return usd

    def _conservative_cost(self, usage: Mapping[str, int]) -> Decimal:
        """料金表のどのモデルよりも安くならない見積もり（USD）。"""
        if not self.pricing:
            raise ValueError("料金表が空です（config/budget.yaml）")
        return max(self.cost(model, usage) for model in self.pricing)

    def _entries(self) -> list[tuple[datetime, Decimal]]:
        if not self.ledger_path.exists():
            return []
        entries = []
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
                ts = datetime.fromisoformat(doc["ts"]).astimezone(UTC)
                entries.append((ts, Decimal(doc["usd"])))
            except (ValueError, KeyError, TypeError, ArithmeticError) as e:
                # 読めない行を飛ばすと上限を超えうるため、安全側に倒して止める
                raise BudgetConfigError(
                    f"コストの台帳 {self.ledger_path} の {n} 行目が読めないため、"
                    f"コストの上限を安全に判定できません（{type(e).__name__}: {e}）。"
                    "その行を直すか消してください"
                ) from e
        return entries

    def spent_today(self) -> Decimal:
        """今日（UTC）の合計（USD）。"""
        today = self._now().date()
        return sum((usd for ts, usd in self._entries() if ts.date() == today), Decimal(0))

    def spent_month(self) -> Decimal:
        """今月（UTC）の合計（USD）。"""
        now = self._now()
        return sum(
            (usd for ts, usd in self._entries() if (ts.year, ts.month) == (now.year, now.month)),
            Decimal(0),
        )

    def check(self) -> None:
        """上限に達していれば :class:`BudgetExceeded` を送出する。LLM を呼ぶ前に使う。"""
        today = self.spent_today()
        if today >= self.daily_usd:
            raise BudgetExceeded(
                f"今日（UTC）のコストが上限に達しました: {today} / {self.daily_usd} USD",
                period="daily",
                spent=today,
                cap=self.daily_usd,
            )
        month = self.spent_month()
        if month >= self.monthly_usd:
            raise BudgetExceeded(
                f"今月（UTC）のコストが上限に達しました: {month} / {self.monthly_usd} USD",
                period="monthly",
                spent=month,
                cap=self.monthly_usd,
            )


def _usd_setting(env_name: str, config_key: str, config_value: object) -> Decimal:
    """上限（USD）を環境変数（あれば）か ``config/budget.yaml`` から読む。

    :raises BudgetConfigError: 0 以上の数値でないとき。
    """
    raw = os.environ.get(env_name)
    where = f"環境変数 {env_name}"
    if raw is None:
        raw, where = str(config_value), f"config/budget.yaml の {config_key}"
    try:
        value = Decimal(raw.strip())
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite() or value < 0:
        raise BudgetConfigError(
            f"{where} の値「{raw}」はコストの上限（USD）として使えません。"
            "0 以上の数値（例 1.00）を指定してください"
        )
    return value
