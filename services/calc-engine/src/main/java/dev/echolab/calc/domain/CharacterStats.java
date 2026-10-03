package dev.echolab.calc.domain;

import java.math.BigDecimal;

/**
 * ダメージ計算に使う攻撃側のステータス。
 *
 * @param atk 最終攻撃力
 * @param critRate 会心率（0.05 = 5%。1 を超えた分は計算時に 1 に丸める）
 * @param critDmg 会心ダメージ倍率（1.5 = 150%）
 * @param dmgBonus ダメージアップの合計（0.3 = 30%）
 */
public record CharacterStats(
    BigDecimal atk, BigDecimal critRate, BigDecimal critDmg, BigDecimal dmgBonus) {

  /** 入力を検証する。 */
  public CharacterStats {
    Precision.requireNonNegative(atk, "atk");
    Precision.requireNonNegative(critRate, "critRate");
    Precision.requireNonNegative(dmgBonus, "dmgBonus");
    Precision.requireNonNegative(critDmg, "critDmg");
    if (critDmg.compareTo(BigDecimal.ONE) < 0) {
      throw new IllegalArgumentException("critDmg は 1 以上である必要があります: " + critDmg);
    }
  }
}
