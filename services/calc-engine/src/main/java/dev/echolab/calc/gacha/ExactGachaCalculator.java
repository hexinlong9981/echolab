package dev.echolab.calc.gacha;

/**
 * ピックアップ獲得確率の厳密解。
 *
 * <p>状態（天井カウント, 確定の有無）を持つマルコフ連鎖を前向きに計算する。 計算量は O(回数 × hardPity)。モンテカルロ法の検証基準にも使う。
 */
public final class ExactGachaCalculator {

  /** {@code pulls} 回以内にピックアップを獲得する確率。 */
  public double probabilityWithin(PityRules rules, GachaState start, int pulls) {
    double[] cumulative = cumulative(rules, start, pulls);
    return cumulative[pulls];
  }

  /**
   * 0〜{@code pulls} 回それぞれの累積獲得確率。
   *
   * @return 長さ {@code pulls + 1} の配列。{@code [n]} が n 回以内に獲得する確率
   */
  public double[] cumulative(PityRules rules, GachaState start, int pulls) {
    if (pulls < 0) {
      throw new IllegalArgumentException("pulls は 0 以上である必要があります: " + pulls);
    }
    start.requireValidFor(rules);
    int hard = rules.hardPity();
    // dist[c][g]: まだ獲得していない状態で、天井カウント c・確定 g にいる確率
    double[][] dist = new double[hard][2];
    dist[start.pity()][start.guaranteed() ? 1 : 0] = 1.0;
    double[] result = new double[pulls + 1];
    double success = 0.0;
    for (int n = 1; n <= pulls; n++) {
      double[][] next = new double[hard][2];
      for (int c = 0; c < hard; c++) {
        for (int g = 0; g <= 1; g++) {
          double p = dist[c][g];
          if (p == 0.0) {
            continue;
          }
          double q = rules.fiveStarRate(c + 1);
          if (g == 1) {
            success += p * q;
          } else {
            success += p * q * rules.featuredRate();
            int afterLoss = rules.guaranteeAfterLoss() ? 1 : 0;
            next[0][afterLoss] += p * q * (1.0 - rules.featuredRate());
          }
          if (c + 1 < hard) {
            next[c + 1][g] += p * (1.0 - q);
          }
        }
      }
      dist = next;
      result[n] = Math.min(1.0, success);
    }
    return result;
  }

  /**
   * ピックアップ獲得までの期待回数。
   *
   * <p>未獲得の確率が {@code epsilon} を下回るまで計算する。{@code maxPulls} に達しても下回らない場合は例外。
   */
  public double expectedPulls(PityRules rules, GachaState start, int maxPulls, double epsilon) {
    double[] cumulative = cumulative(rules, start, maxPulls);
    double expected = 0.0;
    for (int n = 0; n < maxPulls; n++) {
      double notYet = 1.0 - cumulative[n];
      expected += notYet;
      if (1.0 - cumulative[n + 1] < epsilon) {
        return expected;
      }
    }
    throw new IllegalStateException("maxPulls 回では収束しませんでした: " + maxPulls);
  }
}
