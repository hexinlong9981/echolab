package dev.echolab.app.tool;

import dev.echolab.app.data.DataItem;
import dev.echolab.app.data.DomainData;
import dev.echolab.calc.gacha.GachaState;
import dev.echolab.calc.gacha.PityRules;
import java.math.BigDecimal;
import java.util.Set;

/** ガチャの 2 つのツールに共通する入力（規則・開始状態・回数）の取り出し。 */
final class GachaInputs {

  /** {@code pulls} の上限。計算量（回数 × ハード天井）を抑えるため。 */
  static final int MAX_PULLS = 10_000;

  /** {@code hard_pity} の上限。厳密解の状態数を抑えるため。 */
  static final int MAX_HARD_PITY = 10_000;

  private static final Set<String> RULE_FIELDS =
      Set.of(
          "base_rate",
          "soft_pity_start",
          "soft_pity_increment",
          "hard_pity",
          "featured_rate",
          "guarantee_after_loss");

  private GachaInputs() {}

  /** {@code rules}（直接指定）か {@code banner}（データ参照）のどちらか一方から規則を得る。 */
  static PityRules rules(Arguments args, DomainData data, Provenance provenance) {
    String which = args.requireExactlyOne("rules", "banner");
    if (which.equals("rules")) {
      return parseRules(args.object("rules"));
    }
    DataItem banner = data.banner(args.string("banner"));
    return parseRules(Arguments.of(provenance.use(banner), banner.reference() + ".rules"));
  }

  /** 天井の規則を取り出す。確率の範囲は {@link PityRules} 側でも検証される。 */
  static PityRules parseRules(Arguments r) {
    r.requireOnly(RULE_FIELDS);
    return new PityRules(
        probability(r, "base_rate"),
        r.intValue("soft_pity_start", 1, MAX_HARD_PITY),
        probability(r, "soft_pity_increment"),
        r.intValue("hard_pity", 1, MAX_HARD_PITY),
        probability(r, "featured_rate"),
        r.bool("guarantee_after_loss"));
  }

  /** 開始状態（{@code start_pity}・{@code guaranteed}）。 */
  static GachaState start(Arguments args) {
    return new GachaState(
        args.intValue("start_pity", 0, MAX_HARD_PITY - 1), args.bool("guaranteed"));
  }

  /** 引く回数（{@code pulls}）。 */
  static int pulls(Arguments args) {
    return args.intValue("pulls", 0, MAX_PULLS);
  }

  private static double probability(Arguments r, String field) {
    return r.decimal(field, BigDecimal.ZERO, BigDecimal.ONE).doubleValue();
  }
}
