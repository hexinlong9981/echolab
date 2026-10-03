package dev.echolab.calc.damage;

import static dev.echolab.calc.domain.Precision.MC;

import dev.echolab.calc.domain.CharacterStats;
import dev.echolab.calc.domain.Precision;
import java.math.BigDecimal;

/**
 * 期待ダメージの計算。
 *
 * <p>汎用的な乗算モデル {@code 基礎 × ダメージアップ × 会心期待値 × 防御 × 耐性} を使う。 実際のゲームの式・定数は {@code domains/wuwa/data}
 * 側で確認したうえで与える前提で、 ここには特定のゲームの定数を埋め込まない。
 */
public final class DamageCalculator {

  private static final BigDecimal TWO = BigDecimal.valueOf(2);

  /** 期待ダメージと、その明細を計算する。 */
  public DamageBreakdown expected(DamageInput input) {
    CharacterStats a = input.attacker();
    BigDecimal base = baseDamage(a.atk(), input.skillMultiplier());
    BigDecimal bonus = bonusMultiplier(a.dmgBonus());
    BigDecimal crit = critMultiplier(a.critRate(), a.critDmg());
    BigDecimal def =
        defenseMultiplier(input.defenseConstant(), input.enemy().defense(), input.defIgnore());
    BigDecimal res = resistanceMultiplier(input.enemy().resistance(), input.resShred());
    BigDecimal total =
        base.multiply(bonus, MC).multiply(crit, MC).multiply(def, MC).multiply(res, MC);
    return new DamageBreakdown(
        Precision.round(base),
        Precision.round(bonus),
        Precision.round(crit),
        Precision.round(def),
        Precision.round(res),
        Precision.round(total));
  }

  /** 基礎ダメージ = 攻撃力 × スキル倍率。 */
  public static BigDecimal baseDamage(BigDecimal atk, BigDecimal skillMultiplier) {
    return atk.multiply(skillMultiplier, MC);
  }

  /** ダメージアップ乗区 = 1 + ダメージアップ。 */
  public static BigDecimal bonusMultiplier(BigDecimal dmgBonus) {
    return BigDecimal.ONE.add(dmgBonus, MC);
  }

  /** 会心期待値乗区 = 1 + 会心率 × (会心ダメージ − 1)。会心率は [0, 1] に丸める。 */
  public static BigDecimal critMultiplier(BigDecimal critRate, BigDecimal critDmg) {
    BigDecimal rate = Precision.clamp(critRate, BigDecimal.ZERO, BigDecimal.ONE);
    return BigDecimal.ONE.add(rate.multiply(critDmg.subtract(BigDecimal.ONE, MC), MC), MC);
  }

  /** 防御乗区 = C / (C + 防御 × (1 − 防御無視))。 */
  public static BigDecimal defenseMultiplier(
      BigDecimal defenseConstant, BigDecimal defense, BigDecimal defIgnore) {
    BigDecimal effectiveDef = defense.multiply(BigDecimal.ONE.subtract(defIgnore, MC), MC);
    return defenseConstant.divide(defenseConstant.add(effectiveDef, MC), MC);
  }

  /**
   * 耐性乗区。有効耐性 r = 耐性 − 耐性ダウン として、r &lt; 0 なら 1 − r/2、それ以外は 1 − r。
   *
   * @throws IllegalArgumentException 有効耐性が 1 以上（ダメージが 0 以下になる）の場合
   */
  public static BigDecimal resistanceMultiplier(BigDecimal resistance, BigDecimal resShred) {
    BigDecimal effective = resistance.subtract(resShred, MC);
    if (effective.compareTo(BigDecimal.ONE) >= 0) {
      throw new IllegalArgumentException("有効耐性は 1 未満である必要があります: " + effective);
    }
    if (effective.signum() < 0) {
      return BigDecimal.ONE.subtract(effective.divide(TWO, MC), MC);
    }
    return BigDecimal.ONE.subtract(effective, MC);
  }
}
