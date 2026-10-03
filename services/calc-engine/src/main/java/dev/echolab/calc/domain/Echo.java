package dev.echolab.calc.domain;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * 声骸 1 個。
 *
 * @param name 表示名（任意の文字列。ゲーム内の名称である必要はない）
 * @param cost コスト（1〜4）
 * @param main メイン詞条
 * @param subs サブ詞条（最大 5 個）
 */
public record Echo(String name, int cost, MainAffix main, List<SubAffix> subs) {

  /** サブ詞条の上限数。 */
  public static final int MAX_SUBS = 5;

  /** 入力を検証し、サブ詞条を不変リストにする。 */
  public Echo {
    Objects.requireNonNull(name, "name");
    Objects.requireNonNull(main, "main");
    if (cost < 1 || cost > 4) {
      throw new IllegalArgumentException("cost は 1〜4 である必要があります: " + cost);
    }
    subs = List.copyOf(subs);
    if (subs.size() > MAX_SUBS) {
      throw new IllegalArgumentException("サブ詞条は最大 " + MAX_SUBS + " 個です: " + subs.size());
    }
  }

  /** メインとサブをまとめた詞条の一覧。 */
  public List<Affix> affixes() {
    List<Affix> all = new ArrayList<>(subs.size() + 1);
    all.add(main);
    all.addAll(subs);
    return List.copyOf(all);
  }
}
