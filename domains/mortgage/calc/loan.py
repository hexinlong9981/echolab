"""住宅ローンの返済の計算（元利均等・元金均等・繰上返済）。

計算例のための単純なモデルで、金融機関の実際の計算（円未満の端数処理・日割りの利息・
手数料・金利の見直し）は含まない。金融上の助言ではない。

- 金利は固定。月利 = 年利 / 12、返済回数 = 年数 × 12（毎月払い・ボーナス払いなし）。
- 中間の計算は ``Decimal``（有効桁 34）、出力は小数 6 桁・ROUND_HALF_EVEN
  （calc-engine と同じ出力の桁）。円未満を丸めない理論値。
- 入力の誤りは :class:`LoanInputError`（日本語の説明）。
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Any

#: 中間の計算の有効桁（IEEE 754 decimal128 と同じ）。
PRECISION = 34
_OUTPUT_QUANTUM = Decimal("0.000001")
_QUANTIZE_CONTEXT = Context(prec=60, rounding=ROUND_HALF_EVEN)

MAX_YEARS = 50
MAX_ANNUAL_RATE = Decimal("0.2")
METHODS = ("shorten_term", "reduce_payment")


class LoanInputError(ValueError):
    """入力が計算の前提に合わない。メッセージはそのまま LLM と利用者に見せる。"""


def equal_payment(i: Mapping[str, Any]) -> dict[str, Decimal]:
    """元利均等返済：毎月の返済額が一定。"""
    with _context():
        principal, rate, n = _loan(i)
        monthly = _annuity(principal, rate, n)
        total = monthly * n
        return _output(
            monthly_payment=monthly, total_payment=total, total_interest=total - principal
        )


def equal_principal(i: Mapping[str, Any]) -> dict[str, Decimal]:
    """元金均等返済：毎月の元金が一定で、利息の分だけ返済額が減っていく。

    k 回目の返済額 = P/n + (P − (k−1)·P/n)·r、利息の合計 = P·r·(n+1)/2。
    """
    with _context():
        principal, rate, n = _loan(i)
        part = principal / n
        interest = principal * rate * (n + 1) / 2
        return _output(
            first_payment=part + principal * rate,
            last_payment=part + part * rate,
            total_payment=principal + interest,
            total_interest=interest,
        )


def prepayment(i: Mapping[str, Any]) -> dict[str, Decimal]:
    """元利均等返済の途中で一部を繰上返済したときの効果。

    ``after_months`` 回の返済を終えた直後に ``prepay_amount`` を元金に充てる。

    - ``shorten_term``（期間短縮型）：毎月の返済額は変えず、返済期間を短くする。
      最後の回は残りの元金と利息だけを払う。
    - ``reduce_payment``（返済額軽減型）：残りの期間は変えず、毎月の返済額を下げる。
    """
    with _context():
        principal, rate, n = _loan(i)
        k = _integer(i, "after_months", minimum=1)
        if k >= n:
            raise LoanInputError(f"after_months は返済回数 {n} より小さくしてください: {k}")
        prepay = _positive(i, "prepay_amount")
        method = i.get("method")
        if method not in METHODS:
            raise LoanInputError(f"method は {' か '.join(METHODS)} です: {method!r}")

        monthly = _annuity(principal, rate, n)
        balance = principal
        for _ in range(k):
            balance = balance * (1 + rate) - monthly
        if prepay >= balance:
            raise LoanInputError(
                "繰上返済の額が残高以上です（全額の返済になるため、この計算の対象外です）"
            )
        rest = balance - prepay
        remaining = n - k

        if method == "reduce_payment":
            monthly_after = _annuity(rest, rate, remaining)
            months_after = remaining
            paid_after = monthly_after * remaining
        else:
            monthly_after = monthly
            months_after, paid_after = _pay_down(rest, rate, monthly)

        interest_before = monthly * n - principal
        interest_after = monthly * k + prepay + paid_after - principal
        return _output(
            balance_before=balance,
            monthly_payment_after=monthly_after,
            remaining_months_after=Decimal(months_after),
            total_interest_before=interest_before,
            total_interest_after=interest_after,
            interest_saved=interest_before - interest_after,
            months_saved=Decimal(remaining - months_after),
        )


# ---------------------------------------------------------------------------


def _context() -> Any:
    ctx = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)
    return localcontext(ctx)


def _loan(i: Mapping[str, Any]) -> tuple[Decimal, Decimal, int]:
    principal = _positive(i, "principal")
    rate = _number(i, "annual_rate")
    if not Decimal(0) <= rate <= MAX_ANNUAL_RATE:
        raise LoanInputError(f"annual_rate は 0 以上 {MAX_ANNUAL_RATE} 以下です: {rate}")
    years = _integer(i, "years", minimum=1)
    if years > MAX_YEARS:
        raise LoanInputError(f"years は {MAX_YEARS} 以下です: {years}")
    return principal, rate / 12, years * 12


def _annuity(principal: Decimal, rate: Decimal, n: int) -> Decimal:
    """元利均等の毎月の返済額 P·r / (1 − (1+r)^−n)。金利 0 なら P / n。"""
    if rate == 0:
        return principal / n
    return principal * rate / (1 - (1 + rate) ** -n)


def _pay_down(balance: Decimal, rate: Decimal, monthly: Decimal) -> tuple[int, Decimal]:
    """毎月 ``monthly`` を払い、残高が無くなるまでの回数と支払いの合計。"""
    months, paid = 0, Decimal(0)
    while balance > 0:
        months += 1
        due = balance * (1 + rate)
        if due <= monthly:
            return months, paid + due
        paid += monthly
        balance = due - monthly
    return months, paid


def _number(i: Mapping[str, Any], key: str) -> Decimal:
    if key not in i:
        raise LoanInputError(f"{key} がありません")
    value = i[key]
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        raise LoanInputError(f"{key} は数値です: {value!r}")
    try:
        number = Decimal(str(value))
    except ArithmeticError as e:
        raise LoanInputError(f"{key} は数値です: {value!r}") from e
    if not number.is_finite():
        raise LoanInputError(f"{key} は有限の数値です: {value!r}")
    return number


def _positive(i: Mapping[str, Any], key: str) -> Decimal:
    number = _number(i, key)
    if number <= 0:
        raise LoanInputError(f"{key} は 0 より大きい値です: {number}")
    return number


def _integer(i: Mapping[str, Any], key: str, *, minimum: int) -> int:
    number = _number(i, key)
    if number != number.to_integral_value():
        raise LoanInputError(f"{key} は整数です: {number}")
    if number < minimum:
        raise LoanInputError(f"{key} は {minimum} 以上です: {number}")
    return int(number)


def _output(**values: Decimal) -> dict[str, Decimal]:
    return {
        k: v.quantize(_OUTPUT_QUANTUM, context=_QUANTIZE_CONTEXT) + 0 for k, v in values.items()
    }


#: ツール名 → 計算。MCP サーバと試験が共用する。
TOOLS = {
    "mortgage.equal_payment": equal_payment,
    "mortgage.equal_principal": equal_principal,
    "mortgage.prepayment": prepayment,
}
