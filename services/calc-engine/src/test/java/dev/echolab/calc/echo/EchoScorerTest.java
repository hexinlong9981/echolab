package dev.echolab.calc.echo;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.echolab.calc.domain.Echo;
import dev.echolab.calc.domain.MainAffix;
import dev.echolab.calc.domain.Stat;
import dev.echolab.calc.domain.SubAffix;
import java.math.BigDecimal;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class EchoScorerTest {

  private final EchoScorer scorer = new EchoScorer();

  private static BigDecimal d(String v) {
    return new BigDecimal(v);
  }

  private static final Map<Stat, BigDecimal> WEIGHTS =
      Map.of(Stat.CRIT_RATE, d("1"), Stat.CRIT_DMG, d("1"));
  private static final Map<Stat, BigDecimal> MAX =
      Map.of(Stat.CRIT_RATE, d("0.1"), Stat.CRIT_DMG, d("0.2"));

  @Test
  void mainAffixIsNotScored() {
    Echo echo = new Echo("e", 4, new MainAffix(Stat.CRIT_RATE, d("0.22")), List.of());
    EchoScore s = scorer.score(echo, WEIGHTS, MAX);
    assertThat(s.score()).isEqualByComparingTo("0");
    assertThat(s.contributions()).isEmpty();
  }

  @Test
  void contributionsAreReportedPerStat() {
    Echo echo =
        new Echo(
            "e",
            3,
            new MainAffix(Stat.ATK_PERCENT, d("0.3")),
            List.of(
                new SubAffix(Stat.CRIT_RATE, d("0.05")), new SubAffix(Stat.CRIT_DMG, d("0.2"))));
    EchoScore s = scorer.score(echo, WEIGHTS, MAX);
    assertThat(s.score()).isEqualByComparingTo("1.5");
    assertThat(s.percentOfIdeal()).isEqualByComparingTo("75");
    assertThat(s.contributions()).containsEntry(Stat.CRIT_RATE, d("0.500000"));
  }

  @Test
  void zeroWeightsGiveZeroPercent() {
    Echo echo =
        new Echo(
            "e",
            1,
            new MainAffix(Stat.HP_PERCENT, d("0.1")),
            List.of(new SubAffix(Stat.HP_FLAT, d("1"))));
    assertThat(scorer.score(echo, Collections.emptyMap(), MAX).percentOfIdeal())
        .isEqualByComparingTo("0");
  }

  @Test
  void missingMaxRollIsRejected() {
    Echo echo =
        new Echo(
            "e",
            1,
            new MainAffix(Stat.HP_PERCENT, d("0.1")),
            List.of(new SubAffix(Stat.CRIT_RATE, d("0.1"))));
    assertThatThrownBy(() -> scorer.score(echo, WEIGHTS, Map.of()))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void invalidEchoIsRejected() {
    MainAffix main = new MainAffix(Stat.HP_PERCENT, d("0.1"));
    assertThatThrownBy(() -> new Echo("e", 5, main, List.of()))
        .isInstanceOf(IllegalArgumentException.class);
    SubAffix sub = new SubAffix(Stat.CRIT_RATE, d("0.1"));
    assertThatThrownBy(() -> new Echo("e", 1, main, List.of(sub, sub, sub, sub, sub, sub)))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new SubAffix(Stat.CRIT_RATE, d("-1")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void idealScoreUsesTopFiveWeights() {
    Map<Stat, BigDecimal> w =
        Map.of(
            Stat.CRIT_RATE, d("1"),
            Stat.CRIT_DMG, d("1"),
            Stat.ATK_PERCENT, d("0.5"),
            Stat.ATK_FLAT, d("0.5"),
            Stat.ENERGY_REGEN, d("0.5"),
            Stat.HP_PERCENT, d("0.1"));
    assertThat(EchoScorer.idealScore(w)).isEqualByComparingTo("3.5");
  }
}
