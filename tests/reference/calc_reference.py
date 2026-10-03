"""calc-engine（Java）と独立に書いた参照実装。

ゴールデンケースの期待値をこの実装でも再計算し、Java と Python の 2 つの実装と
YAML の期待値が一致することを確かめる（言語をまたいだ契約テスト）。
Java 側をコピーせず、式の定義（docs/adr/0001）から書き起こしている。
"""

from __future__ import annotations

from decimal import Decimal, localcontext


def _d(x: object) -> Decimal:
    return Decimal(str(x))


def damage_expected(inp: dict) -> dict[str, Decimal]:
    """期待ダメージと各乗区。"""
    with localcontext() as ctx:
        ctx.prec = 16
        base = _d(inp["atk"]) * _d(inp["skill_multiplier"])
        bonus = 1 + _d(inp["dmg_bonus"])
        rate = min(max(_d(inp["crit_rate"]), Decimal(0)), Decimal(1))
        crit = 1 + rate * (_d(inp["crit_dmg"]) - 1)
        c = _d(inp["defense_constant"])
        eff_def = _d(inp["enemy_def"]) * (1 - _d(inp["def_ignore"]))
        defense = c / (c + eff_def)
        eff_res = _d(inp["enemy_res"]) - _d(inp["res_shred"])
        res = 1 - eff_res / 2 if eff_res < 0 else 1 - eff_res
        total = base * bonus * crit * defense * res
    return {
        "base": base,
        "bonus_multiplier": bonus,
        "crit_multiplier": crit,
        "defense_multiplier": defense,
        "resistance_multiplier": res,
        "total": total,
    }


def echo_score(inp: dict) -> dict[str, Decimal]:
    """サブ詞条の重み付きスコア。メイン詞条は評価しない。"""
    weights = {k: _d(v) for k, v in inp["weights"].items()}
    max_roll = {k: _d(v) for k, v in inp["max_roll"].items()}
    with localcontext() as ctx:
        ctx.prec = 16
        score = Decimal(0)
        for sub in inp["echo"]["subs"]:
            w = weights.get(sub["stat"], Decimal(0))
            if w != 0:
                score += w * _d(sub["value"]) / max_roll[sub["stat"]]
        ideal = sum(sorted((w for w in weights.values() if w > 0), reverse=True)[:5], Decimal(0))
        percent = Decimal(0) if ideal == 0 else score * 100 / ideal
    return {"score": score, "percent_of_ideal": percent}


def _five_star_rate(rules: dict, k: int) -> float:
    if k == rules["hard_pity"]:
        return 1.0
    rate = rules["base_rate"]
    if k >= rules["soft_pity_start"]:
        rate += (k - rules["soft_pity_start"] + 1) * rules["soft_pity_increment"]
    return min(1.0, rate)


def gacha_probability_within(inp: dict) -> float:
    """pulls 回以内にピックアップを獲得する確率（状態を列挙する前向き計算）。"""
    rules = inp["rules"]
    hard = rules["hard_pity"]
    f = rules["featured_rate"]
    states = {(inp["start_pity"], bool(inp["guaranteed"])): 1.0}
    success = 0.0
    for _ in range(inp["pulls"]):
        nxt: dict[tuple[int, bool], float] = {}
        for (c, g), p in states.items():
            q = _five_star_rate(rules, c + 1)
            if g:
                success += p * q
            else:
                success += p * q * f
                key = (0, bool(rules["guarantee_after_loss"]))
                nxt[key] = nxt.get(key, 0.0) + p * q * (1 - f)
            if c + 1 < hard:
                nxt[(c + 1, g)] = nxt.get((c + 1, g), 0.0) + p * (1 - q)
        states = nxt
    return min(1.0, success)
