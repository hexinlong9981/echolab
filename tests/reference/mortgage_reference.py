"""住宅ローンのパック（domains/mortgage/calc/loan.py）の参照実装。

パックの実装とは別の方法で計算し、同じゴールデンケースと照合する（ADR-0009）。

- パックは Decimal で 1 回ずつ残高を進める。ここは float と閉形式（残高の公式・対数で
  求める回数）を使う。
- 速さより読みやすさを優先する。入力の検査はしない（ゴールデンケースの入力は正しい前提）。
"""

from __future__ import annotations

import math


def _loan(i: dict) -> tuple[float, float, int]:
    return float(i["principal"]), float(i["annual_rate"]) / 12, int(i["years"]) * 12


def _annuity(p: float, r: float, n: int) -> float:
    return p / n if r == 0 else p * r / (1 - (1 + r) ** -n)


def _balance(p: float, r: float, m: float, k: int) -> float:
    """k 回払った後の残高 P(1+r)^k − M((1+r)^k − 1)/r。"""
    if r == 0:
        return p - m * k
    g = (1 + r) ** k
    return p * g - m * (g - 1) / r


def equal_payment(i: dict) -> dict[str, float]:
    p, r, n = _loan(i)
    m = _annuity(p, r, n)
    return {"monthly_payment": m, "total_payment": m * n, "total_interest": m * n - p}


def equal_principal(i: dict) -> dict[str, float]:
    p, r, n = _loan(i)
    payments = [p / n + (p - k * p / n) * r for k in range(n)]
    return {
        "first_payment": payments[0],
        "last_payment": payments[-1],
        "total_payment": sum(payments),
        "total_interest": sum(payments) - p,
    }


def prepayment(i: dict) -> dict[str, float]:
    p, r, n = _loan(i)
    k, prepay = int(i["after_months"]), float(i["prepay_amount"])
    m = _annuity(p, r, n)
    before = _balance(p, r, m, k)
    rest = before - prepay
    remaining = n - k
    if i["method"] == "reduce_payment":
        monthly_after = _annuity(rest, r, remaining)
        months = remaining
        paid_after = monthly_after * remaining
    else:
        monthly_after = m
        # 残高が 0 になる回数：rest·(1+r)^t = M((1+r)^t − 1)/r を t について解いて切り上げる
        exact = rest / m if r == 0 else -math.log(1 - rest * r / m) / math.log(1 + r)
        months = math.ceil(exact - 1e-9)
        last = _balance(rest, r, m, months - 1) * (1 + r)
        paid_after = m * (months - 1) + last
    interest_before = m * n - p
    interest_after = m * k + prepay + paid_after - p
    return {
        "balance_before": before,
        "monthly_payment_after": monthly_after,
        "remaining_months_after": float(months),
        "total_interest_before": interest_before,
        "total_interest_after": interest_after,
        "interest_saved": interest_before - interest_after,
        "months_saved": float(remaining - months),
    }


TOOLS = {
    "mortgage.equal_payment": equal_payment,
    "mortgage.equal_principal": equal_principal,
    "mortgage.prepayment": prepayment,
}
