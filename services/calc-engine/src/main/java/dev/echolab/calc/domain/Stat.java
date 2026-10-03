package dev.echolab.calc.domain;

/**
 * ステータスの種類。
 *
 * <p>割合系（{@code *_PERCENT}・会心・ダメージアップなど）は 0.1 = 10% の小数で持つ。
 */
public enum Stat {
  ATK_FLAT,
  ATK_PERCENT,
  HP_FLAT,
  HP_PERCENT,
  DEF_FLAT,
  DEF_PERCENT,
  CRIT_RATE,
  CRIT_DMG,
  ENERGY_REGEN,
  BASIC_ATTACK_DMG_BONUS,
  HEAVY_ATTACK_DMG_BONUS,
  SKILL_DMG_BONUS,
  LIBERATION_DMG_BONUS,
  ELEMENTAL_DMG_BONUS,
  HEALING_BONUS
}
