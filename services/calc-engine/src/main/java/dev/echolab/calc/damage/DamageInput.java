package dev.echolab.calc.damage;

import dev.echolab.calc.domain.CharacterStats;
import dev.echolab.calc.domain.EnemyStats;
import dev.echolab.calc.domain.Precision;
import java.math.BigDecimal;
import java.util.Objects;

/**
 * 期待ダメージ計算の入力。
 *
 * @param attacker 攻撃側ステータス
 * @param skillMultiplier スキル倍率（2.5 = 250%）
 * @param enemy 防御側ステータス
 * @param defenseConstant 防御乗区の定数（攻撃側のレベル等から決まる値。ゲームごとに要確認）
 * @param defIgnore 防御無視（0〜1）
 * @param resShred 耐性ダウン（0.1 = 10%）
 */
public record DamageInput(
    CharacterStats attacker,
    BigDecimal skillMultiplier,
    EnemyStats enemy,
    BigDecimal defenseConstant,
    BigDecimal defIgnore,
    BigDecimal resShred) {

  /** 入力を検証する。 */
  public DamageInput {
    Objects.requireNonNull(attacker, "attacker");
    Objects.requireNonNull(enemy, "enemy");
    Precision.requireNonNegative(skillMultiplier, "skillMultiplier");
    Precision.requireNonNegative(defenseConstant, "defenseConstant");
    if (defenseConstant.signum() == 0) {
      throw new IllegalArgumentException("defenseConstant は 0 より大きい必要があります");
    }
    Precision.requireNonNegative(defIgnore, "defIgnore");
    if (defIgnore.compareTo(BigDecimal.ONE) > 0) {
      throw new IllegalArgumentException("defIgnore は 0〜1 である必要があります: " + defIgnore);
    }
    Objects.requireNonNull(resShred, "resShred");
  }
}
