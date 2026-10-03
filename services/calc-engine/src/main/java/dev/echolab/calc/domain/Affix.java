package dev.echolab.calc.domain;

import java.math.BigDecimal;

/**
 * 声骸の詞条（メイン／サブ）。
 *
 * <p>sealed にしてあるので、{@code switch} で種類を網羅しないとコンパイルが通らない。 詞条の種類を増やしたときに、評価ロジックの書き漏れをコンパイル時に検出できる。
 */
public sealed interface Affix permits MainAffix, SubAffix {

  /** ステータスの種類。 */
  Stat stat();

  /** 値（割合系は小数）。 */
  BigDecimal value();
}
