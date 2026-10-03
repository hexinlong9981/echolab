package dev.echolab.app.tool;

import dev.echolab.app.data.DomainData;
import dev.echolab.calc.gacha.GachaState;
import dev.echolab.calc.gacha.MonteCarloGachaSimulator;
import dev.echolab.calc.gacha.PityRules;
import java.util.Objects;
import java.util.Set;

/**
 * {@code gacha.simulate}：{@code gacha.probability_within} と同じ確率のモンテカルロ推定。
 *
 * <p>同じ {@code seed} なら実行方式（逐次・parallel stream・仮想スレッド）によらず同じ結果になる。 推定値の標準誤差 {@code sqrt(p(1 − p) /
 * trials)} も返す。
 */
public final class GachaSimulateTool implements ToolHandler {

  /** {@code trials} の上限。 */
  static final int MAX_TRIALS = 1_000_000;

  /** {@code trials} を省略したときの試行回数。 */
  static final int DEFAULT_TRIALS = 100_000;

  /** {@code seed} を省略したときの乱数の種。 */
  static final long DEFAULT_SEED = 0L;

  private static final Set<String> FIELDS =
      Set.of("rules", "banner", "start_pity", "guaranteed", "pulls", "trials", "seed", "method");

  private final MonteCarloGachaSimulator simulator = new MonteCarloGachaSimulator();
  private final DomainData data;

  /** データの参照先を指定して作る。 */
  public GachaSimulateTool(DomainData data) {
    this.data = Objects.requireNonNull(data, "data");
  }

  @Override
  public String domainName() {
    return "gacha.simulate";
  }

  @Override
  public String description() {
    return "gacha_probability_within と同じ確率をモンテカルロ法で推定し、推定値と標準誤差を返す。"
        + "同じ seed なら実行方式によらず同じ結果になる。"
        + "規則は rules で直接与えるか、banner でデータの ID を指定する（どちらか一方）。";
  }

  @Override
  public ToolEnvelope call(Arguments args) {
    args.requireOnly(FIELDS);
    Provenance provenance = new Provenance();
    PityRules rules = GachaInputs.rules(args, data, provenance);
    GachaState start = GachaInputs.start(args);
    int pulls = GachaInputs.pulls(args);
    int trials = args.has("trials") ? args.intValue("trials", 1, MAX_TRIALS) : DEFAULT_TRIALS;
    long seed =
        args.has("seed") ? args.integer("seed", Long.MIN_VALUE, Long.MAX_VALUE) : DEFAULT_SEED;
    MonteCarloGachaSimulator.Mode mode =
        args.has("method") ? mode(args.string("method")) : MonteCarloGachaSimulator.Mode.SEQUENTIAL;
    double p = simulator.probabilityWithin(rules, start, pulls, trials, seed, mode);
    double stdError = Math.sqrt(p * (1.0 - p) / trials);
    return provenance.envelope(
        domainName(),
        new ToolEnvelope.Values().put("probability", p).put("std_error", stdError).build());
  }

  /** {@code sequential}・{@code parallel_stream}・{@code virtual_threads} を実行方式にする。 */
  static MonteCarloGachaSimulator.Mode mode(String method) {
    return switch (method) {
      case "sequential" -> MonteCarloGachaSimulator.Mode.SEQUENTIAL;
      case "parallel_stream" -> MonteCarloGachaSimulator.Mode.PARALLEL_STREAM;
      case "virtual_threads" -> MonteCarloGachaSimulator.Mode.VIRTUAL_THREADS;
      default ->
          throw new ToolException(
              "method は sequential・parallel_stream・virtual_threads のいずれかである必要があります: " + method);
    };
  }
}
