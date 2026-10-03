package dev.echolab.calc.domain;

import java.math.BigDecimal;
import java.util.Objects;

/** メイン詞条。値はコストと強化段階で決まるため、スコア評価の対象にしない。 */
public record MainAffix(Stat stat, BigDecimal value) implements Affix {

  /** 入力を検証する。 */
  public MainAffix {
    Objects.requireNonNull(stat, "stat");
    Precision.requireNonNegative(value, "value");
  }
}
