package dev.echolab.calc.echo;

import dev.echolab.calc.domain.Stat;
import java.math.BigDecimal;
import java.util.Map;

/**
 * 声骸スコアの結果。
 *
 * @param score 重み付きスコア（各サブ詞条の 重み × 値 ÷ 最大値 の合計）
 * @param percentOfIdeal 理想値（重みの大きい順に 5 枠を最大値で埋めた場合）に対する割合（%）
 * @param contributions ステータスごとの寄与（出典として回答に添える）
 */
public record EchoScore(
    BigDecimal score, BigDecimal percentOfIdeal, Map<Stat, BigDecimal> contributions) {

  /** 寄与を不変にする。 */
  public EchoScore {
    contributions = Map.copyOf(contributions);
  }
}
