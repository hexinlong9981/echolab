package dev.echolab.calc.domain;

import java.math.BigDecimal;
import java.util.Objects;

/** サブ詞条。スコア評価の対象。 */
public record SubAffix(Stat stat, BigDecimal value) implements Affix {

  /** 入力を検証する。 */
  public SubAffix {
    Objects.requireNonNull(stat, "stat");
    Precision.requireNonNegative(value, "value");
  }
}
