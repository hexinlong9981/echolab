package dev.echolab.app.tool;

import dev.echolab.app.data.DomainData;
import dev.echolab.calc.gacha.ExactGachaCalculator;
import dev.echolab.calc.gacha.PityRules;
import java.util.Objects;
import java.util.Set;

/**
 * {@code gacha.probability_within}：N 回以内にピックアップを獲得する確率（マルコフ連鎖による厳密解）。
 *
 * <p>規則は {@code rules}（直接指定）か {@code banner}（{@code gacha_rules.yaml} の ID）のどちらか一方。
 */
public final class GachaProbabilityWithinTool implements ToolHandler {

  private static final Set<String> FIELDS =
      Set.of("rules", "banner", "start_pity", "guaranteed", "pulls");

  private final ExactGachaCalculator calculator = new ExactGachaCalculator();
  private final DomainData data;

  /** データの参照先を指定して作る。 */
  public GachaProbabilityWithinTool(DomainData data) {
    this.data = Objects.requireNonNull(data, "data");
  }

  @Override
  public String domainName() {
    return "gacha.probability_within";
  }

  @Override
  public String description() {
    return "天井（ソフト・ハード）とすり抜け確定のある規則で、pulls 回以内にピックアップを獲得する確率を厳密に計算する。"
        + "規則は rules で直接与えるか、banner でデータの ID を指定する（どちらか一方）。";
  }

  @Override
  public ToolEnvelope call(Arguments args) {
    args.requireOnly(FIELDS);
    Provenance provenance = new Provenance();
    PityRules rules = GachaInputs.rules(args, data, provenance);
    double p =
        calculator.probabilityWithin(rules, GachaInputs.start(args), GachaInputs.pulls(args));
    return provenance.envelope(
        domainName(), new ToolEnvelope.Values().put("probability", p).build());
  }
}
