package dev.echolab.calc.domain;

import java.math.BigDecimal;
import java.util.Objects;

/**
 * 防御側のステータス。
 *
 * @param defense 防御力
 * @param resistance 属性耐性（0.1 = 10%。負の値も可）
 */
public record EnemyStats(BigDecimal defense, BigDecimal resistance) {

  /** 入力を検証する。 */
  public EnemyStats {
    Precision.requireNonNegative(defense, "defense");
    Objects.requireNonNull(resistance, "resistance");
  }
}
