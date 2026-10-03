package dev.echolab.calc.gacha;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import dev.echolab.calc.gacha.MonteCarloGachaSimulator.Mode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class MonteCarloGachaSimulatorTest {

  private final MonteCarloGachaSimulator mc = new MonteCarloGachaSimulator();
  private final ExactGachaCalculator exact = new ExactGachaCalculator();

  private static final PityRules TOY = ExactGachaCalculatorTest.TOY;

  @Test
  void allModesReturnIdenticalResultsForTheSameSeed() {
    double seq = mc.probabilityWithin(TOY, GachaState.FRESH, 10, 55_555, 42L, Mode.SEQUENTIAL);
    double par = mc.probabilityWithin(TOY, GachaState.FRESH, 10, 55_555, 42L, Mode.PARALLEL_STREAM);
    double vt = mc.probabilityWithin(TOY, GachaState.FRESH, 10, 55_555, 42L, Mode.VIRTUAL_THREADS);
    assertThat(par).isEqualTo(seq);
    assertThat(vt).isEqualTo(seq);
  }

  @ParameterizedTest
  @EnumSource(Mode.class)
  void agreesWithExactSolution(Mode mode) {
    double expected = exact.probabilityWithin(TOY, GachaState.FRESH, 10);
    double estimate = mc.probabilityWithin(TOY, GachaState.FRESH, 10, 200_000, 7L, mode);
    // 標準誤差は約 0.001。5 シグマ相当の 0.005 を許容する
    assertThat(estimate).isCloseTo(expected, within(0.005));
  }

  @Test
  void agreesWithExactSolutionWithoutGuarantee() {
    PityRules noGuarantee = new PityRules(0.1, 5, 0.1, 10, 0.5, false);
    GachaState start = new GachaState(3, false);
    double expected = exact.probabilityWithin(noGuarantee, start, 25);
    double estimate = mc.probabilityWithin(noGuarantee, start, 25, 200_000, 11L, Mode.SEQUENTIAL);
    assertThat(estimate).isCloseTo(expected, within(0.005));
  }

  @Test
  void differentSeedsGiveDifferentChunkSeeds() {
    assertThat(MonteCarloGachaSimulator.chunkSeed(1L, 0))
        .isNotEqualTo(MonteCarloGachaSimulator.chunkSeed(2L, 0))
        .isNotEqualTo(MonteCarloGachaSimulator.chunkSeed(1L, 1));
  }

  @Test
  void invalidArgumentsAreRejected() {
    assertThatThrownBy(() -> mc.probabilityWithin(TOY, GachaState.FRESH, 1, 0, 1L, Mode.SEQUENTIAL))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(
            () -> mc.probabilityWithin(TOY, GachaState.FRESH, -1, 10, 1L, Mode.SEQUENTIAL))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
