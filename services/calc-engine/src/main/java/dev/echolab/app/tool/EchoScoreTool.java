package dev.echolab.app.tool;

import dev.echolab.app.data.DataItem;
import dev.echolab.app.data.DomainData;
import dev.echolab.calc.domain.Echo;
import dev.echolab.calc.domain.MainAffix;
import dev.echolab.calc.domain.Stat;
import dev.echolab.calc.domain.SubAffix;
import dev.echolab.calc.echo.EchoScore;
import dev.echolab.calc.echo.EchoScorer;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * {@code echo.score}：声骸サブ詞条の重み付きスコア。
 *
 * <p>重みは {@code weights}（直接指定）か {@code profile}（{@code echo_weights.yaml} の ID）のどちらか一方。 {@code
 * max_roll} を省略すると {@code echo_weights.yaml} の {@code max_roll} を使う。
 */
public final class EchoScoreTool implements ToolHandler {

  private static final Set<String> FIELDS = Set.of("echo", "weights", "profile", "max_roll");
  private static final Set<String> ECHO_FIELDS = Set.of("name", "cost", "main", "subs");
  private static final Set<String> AFFIX_FIELDS = Set.of("stat", "value");

  private final EchoScorer scorer = new EchoScorer();
  private final DomainData data;

  /** データの参照先を指定して作る。 */
  public EchoScoreTool(DomainData data) {
    this.data = Objects.requireNonNull(data, "data");
  }

  @Override
  public String domainName() {
    return "echo.score";
  }

  @Override
  public String description() {
    return "声骸のサブ詞条を重み付きで評価し、スコアと理想値に対する割合（%）を返す。"
        + "重みは weights で直接与えるか、profile でデータの ID を指定する（どちらか一方）。"
        + "max_roll を省略するとデータの値を使う。";
  }

  @Override
  public ToolEnvelope call(Arguments args) {
    args.requireOnly(FIELDS);
    Provenance provenance = new Provenance();
    Echo echo = parseEcho(args.object("echo"));
    Map<Stat, BigDecimal> weights;
    if (args.requireExactlyOne("weights", "profile").equals("weights")) {
      weights = statMap(args.object("weights"));
    } else {
      DataItem profile = data.profile(args.string("profile"));
      weights = statMap(Arguments.of(provenance.use(profile), profile.reference() + ".weights"));
    }
    Map<Stat, BigDecimal> maxRoll;
    if (args.has("max_roll")) {
      maxRoll = statMap(args.object("max_roll"));
    } else {
      DataItem item = data.maxRoll();
      maxRoll = statMap(Arguments.of(provenance.use(item), item.reference() + ".values"));
    }
    EchoScore s = scorer.score(echo, weights, maxRoll);
    ToolEnvelope.Values values =
        new ToolEnvelope.Values()
            .put("score", s.score())
            .put("percent_of_ideal", s.percentOfIdeal());
    return provenance.envelope(domainName(), values.build());
  }

  private static Echo parseEcho(Arguments e) {
    e.requireOnly(ECHO_FIELDS);
    Arguments main = e.object("main").requireOnly(AFFIX_FIELDS);
    List<SubAffix> subs = new ArrayList<>();
    for (Arguments sub : e.objects("subs")) {
      sub.requireOnly(AFFIX_FIELDS);
      subs.add(new SubAffix(affixStat(sub), nonNegative(sub, "value")));
    }
    return new Echo(
        e.string("name"),
        e.intValue("cost", 1, 4),
        new MainAffix(affixStat(main), nonNegative(main, "value")),
        subs);
  }

  /** ステータス名 → 0 以上の数値。 */
  private static Map<Stat, BigDecimal> statMap(Arguments m) {
    Map<Stat, BigDecimal> map = new EnumMap<>(Stat.class);
    for (String key : m.fieldNames()) {
      map.put(stat(m.qualified(key), key), nonNegative(m, key));
    }
    return map;
  }

  private static BigDecimal nonNegative(Arguments a, String field) {
    BigDecimal value = a.decimal(field);
    if (value.signum() < 0) {
      throw new ToolException(a.qualified(field) + " は 0 以上である必要があります: " + value.toPlainString());
    }
    return value;
  }

  private static Stat affixStat(Arguments affix) {
    String name = affix.string("stat");
    return stat(affix.qualified("stat") + " の値 '" + name + "'", name);
  }

  /**
   * ステータス名を {@link Stat} にする。
   *
   * @param where エラーメッセージでの呼び名
   */
  private static Stat stat(String where, String name) {
    try {
      return Stat.valueOf(name);
    } catch (IllegalArgumentException e) {
      throw new ToolException(
          where
              + " は未知のステータスです（使える値: "
              + String.join(", ", Arrays.stream(Stat.values()).map(Stat::name).toList())
              + "）",
          e);
    }
  }
}
