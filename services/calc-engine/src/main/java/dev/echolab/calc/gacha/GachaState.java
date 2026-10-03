package dev.echolab.calc.gacha;

/**
 * 現在の引き状況。
 *
 * @param pity 前回の最高レアからの回数（0 = 直前に最高レアが出た）
 * @param guaranteed 次の最高レアがピックアップ確定か
 */
public record GachaState(int pity, boolean guaranteed) {

  /** 初期状態（天井カウント 0・確定なし）。 */
  public static final GachaState FRESH = new GachaState(0, false);

  /** 入力を検証する。 */
  public GachaState {
    if (pity < 0) {
      throw new IllegalArgumentException("pity は 0 以上である必要があります: " + pity);
    }
  }

  /** 規則に対して状態が有効かを確かめる。 */
  void requireValidFor(PityRules rules) {
    if (pity >= rules.hardPity()) {
      throw new IllegalArgumentException(
          "pity は hardPity 未満である必要があります: pity=" + pity + ", hardPity=" + rules.hardPity());
    }
  }
}
