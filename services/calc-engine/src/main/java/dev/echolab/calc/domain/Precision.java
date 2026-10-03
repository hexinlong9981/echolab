package dev.echolab.calc.domain;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * 数値精度の方針を 1 か所に集めたクラス。
 *
 * <p>計算途中は {@link MathContext#DECIMAL64}（有効 16 桁）で丸め、外部へ返す値は小数点以下 {@value #OUTPUT_SCALE}
 * 桁にそろえる。方針を変えるときはここだけを直す。
 */
public final class Precision {

  /** 計算途中で使う丸め規則。 */
  public static final MathContext MC = MathContext.DECIMAL64;

  /** 外部へ返す値の小数点以下の桁数。 */
  public static final int OUTPUT_SCALE = 6;

  private Precision() {}

  /** 出力用に丸める。 */
  public static BigDecimal round(BigDecimal value) {
    return value.setScale(OUTPUT_SCALE, RoundingMode.HALF_EVEN);
  }

  /** {@code value} を {@code [min, max]} に収める。 */
  public static BigDecimal clamp(BigDecimal value, BigDecimal min, BigDecimal max) {
    if (value.compareTo(min) < 0) {
      return min;
    }
    if (value.compareTo(max) > 0) {
      return max;
    }
    return value;
  }

  /** 負でないことを確かめる。 */
  public static BigDecimal requireNonNegative(BigDecimal value, String name) {
    if (value == null) {
      throw new IllegalArgumentException(name + " は必須です");
    }
    if (value.signum() < 0) {
      throw new IllegalArgumentException(name + " は 0 以上である必要があります: " + value);
    }
    return value;
  }
}
