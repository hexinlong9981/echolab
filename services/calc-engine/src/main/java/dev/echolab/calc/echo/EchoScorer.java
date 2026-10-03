package dev.echolab.calc.echo;

import static dev.echolab.calc.domain.Precision.MC;

import dev.echolab.calc.domain.Affix;
import dev.echolab.calc.domain.Echo;
import dev.echolab.calc.domain.MainAffix;
import dev.echolab.calc.domain.Precision;
import dev.echolab.calc.domain.Stat;
import dev.echolab.calc.domain.SubAffix;
import java.math.BigDecimal;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.Map;

/**
 * 声骸のサブ詞条を重み付きで評価する。
 *
 * <p>重みと最大値は呼び出し側（キャラクターごとの設定データ）から渡す。 ここには「どのステータスが良いか」という判断を持たない。
 */
public final class EchoScorer {

  private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

  /**
   * スコアを計算する。
   *
   * @param echo 評価する声骸
   * @param weights ステータスごとの重み（無いステータスは 0）
   * @param maxRoll ステータスごとのサブ詞条 1 枠の最大値（正規化に使う）
   */
  public EchoScore score(Echo echo, Map<Stat, BigDecimal> weights, Map<Stat, BigDecimal> maxRoll) {
    Map<Stat, BigDecimal> contributions = new EnumMap<>(Stat.class);
    BigDecimal score = BigDecimal.ZERO;
    for (Affix affix : echo.affixes()) {
      BigDecimal c = contribution(affix, weights, maxRoll);
      if (c.signum() != 0) {
        contributions.merge(affix.stat(), c, (x, y) -> x.add(y, MC));
        score = score.add(c, MC);
      }
    }
    BigDecimal ideal = idealScore(weights);
    BigDecimal percent =
        ideal.signum() == 0 ? BigDecimal.ZERO : score.multiply(HUNDRED, MC).divide(ideal, MC);
    contributions.replaceAll((stat, v) -> Precision.round(v));
    return new EchoScore(Precision.round(score), Precision.round(percent), contributions);
  }

  /** 詞条 1 つの寄与。sealed なので種類を網羅しないとコンパイルできない。 */
  private static BigDecimal contribution(
      Affix affix, Map<Stat, BigDecimal> weights, Map<Stat, BigDecimal> maxRoll) {
    return switch (affix) {
      // メイン詞条はコストで決まるため、厳選の評価には含めない
      case MainAffix main -> BigDecimal.ZERO;
      case SubAffix sub -> subContribution(sub, weights, maxRoll);
    };
  }

  private static BigDecimal subContribution(
      SubAffix sub, Map<Stat, BigDecimal> weights, Map<Stat, BigDecimal> maxRoll) {
    BigDecimal weight = weights.getOrDefault(sub.stat(), BigDecimal.ZERO);
    if (weight.signum() == 0) {
      return BigDecimal.ZERO;
    }
    BigDecimal max = maxRoll.get(sub.stat());
    if (max == null || max.signum() <= 0) {
      throw new IllegalArgumentException("maxRoll に正の値がありません: " + sub.stat());
    }
    return weight.multiply(sub.value(), MC).divide(max, MC);
  }

  /** 重みの大きい順に {@link Echo#MAX_SUBS} 枠を最大値で埋めた場合のスコア。 */
  static BigDecimal idealScore(Map<Stat, BigDecimal> weights) {
    return weights.values().stream()
        .filter(w -> w.signum() > 0)
        .sorted(Comparator.reverseOrder())
        .limit(Echo.MAX_SUBS)
        .reduce(BigDecimal.ZERO, (x, y) -> x.add(y, MC));
  }
}
