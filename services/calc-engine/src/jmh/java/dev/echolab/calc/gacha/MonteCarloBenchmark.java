package dev.echolab.calc.gacha;

import dev.echolab.calc.gacha.MonteCarloGachaSimulator.Mode;
import java.util.concurrent.TimeUnit;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.State;

/**
 * モンテカルロ法の 3 方式（逐次・parallel stream・仮想スレッド）の速度比較。
 *
 * <p>実行: {@code ./gradlew jmh}。結果は同じ（seed 固定）なので、比べるのは時間だけ。
 */
@State(Scope.Benchmark)
@BenchmarkMode(org.openjdk.jmh.annotations.Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
public class MonteCarloBenchmark {

  private static final PityRules RULES = new PityRules(0.008, 66, 0.04, 80, 0.5, true);

  @Param({"100000"})
  public int trials;

  @Param({"SEQUENTIAL", "PARALLEL_STREAM", "VIRTUAL_THREADS"})
  public Mode mode;

  private final MonteCarloGachaSimulator simulator = new MonteCarloGachaSimulator();

  @Benchmark
  public double probabilityWithin160() {
    return simulator.probabilityWithin(RULES, GachaState.FRESH, 160, trials, 42L, mode);
  }
}
