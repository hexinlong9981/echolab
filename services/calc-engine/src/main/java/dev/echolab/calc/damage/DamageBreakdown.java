package dev.echolab.calc.damage;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 期待ダメージの計算明細。
 *
 * <p>回答に出る数字の出典（数値トレース）として、各乗区の値をすべて返す。
 *
 * @param base 基礎ダメージ（攻撃力 × スキル倍率）
 * @param bonusMultiplier ダメージアップ乗区
 * @param critMultiplier 会心期待値乗区
 * @param defenseMultiplier 防御乗区
 * @param resistanceMultiplier 耐性乗区
 * @param total 期待ダメージ
 */
public record DamageBreakdown(
    BigDecimal base,
    BigDecimal bonusMultiplier,
    BigDecimal critMultiplier,
    BigDecimal defenseMultiplier,
    BigDecimal resistanceMultiplier,
    BigDecimal total) {

  /** 名前付きの明細（出力・トレース用。順序は計算順）。 */
  public Map<String, BigDecimal> asMap() {
    Map<String, BigDecimal> map = new LinkedHashMap<>();
    map.put("base", base);
    map.put("bonus_multiplier", bonusMultiplier);
    map.put("crit_multiplier", critMultiplier);
    map.put("defense_multiplier", defenseMultiplier);
    map.put("resistance_multiplier", resistanceMultiplier);
    map.put("total", total);
    return Map.copyOf(map);
  }
}
