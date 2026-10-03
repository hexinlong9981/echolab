package dev.echolab.calc.gacha;

/**
 * 天井（ピティ）の規則。数値はすべて呼び出し側から渡し、特定のゲームの値は埋め込まない。
 *
 * @param baseRate 基本の最高レア排出率（0.008 = 0.8%）
 * @param softPityStart ソフト天井が始まる回数（この回から確率が上がる。1 始まり）
 * @param softPityIncrement ソフト天井で 1 回ごとに加算される確率
 * @param hardPity ハード天井（この回で必ず最高レア）
 * @param featuredRate 最高レアがピックアップ対象である確率（0.5 = 50%）
 * @param guaranteeAfterLoss ピックアップを外した次の最高レアが確定するか
 */
public record PityRules(
    double baseRate,
    int softPityStart,
    double softPityIncrement,
    int hardPity,
    double featuredRate,
    boolean guaranteeAfterLoss) {

  /** 入力を検証する。 */
  public PityRules {
    requireProbability(baseRate, "baseRate");
    requireProbability(featuredRate, "featuredRate");
    requireProbability(softPityIncrement, "softPityIncrement");
    if (hardPity < 1) {
      throw new IllegalArgumentException("hardPity は 1 以上である必要があります: " + hardPity);
    }
    if (softPityStart < 1 || softPityStart > hardPity) {
      throw new IllegalArgumentException("softPityStart は 1〜hardPity である必要があります: " + softPityStart);
    }
  }

  /**
   * 前回の最高レアから数えて {@code pullNumber} 回目（1 始まり）の最高レア排出率。
   *
   * @throws IllegalArgumentException {@code pullNumber} が 1〜hardPity の範囲外の場合
   */
  public double fiveStarRate(int pullNumber) {
    if (pullNumber < 1 || pullNumber > hardPity) {
      throw new IllegalArgumentException("pullNumber は 1〜hardPity である必要があります: " + pullNumber);
    }
    if (pullNumber == hardPity) {
      return 1.0;
    }
    double rate = baseRate;
    if (pullNumber >= softPityStart) {
      rate += (pullNumber - softPityStart + 1) * softPityIncrement;
    }
    return Math.min(1.0, rate);
  }

  private static void requireProbability(double p, String name) {
    if (!(p >= 0.0 && p <= 1.0)) {
      throw new IllegalArgumentException(name + " は 0〜1 である必要があります: " + p);
    }
  }
}
