package dev.echolab.calc.gacha;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.Combinators;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;
import org.junit.jupiter.api.Test;

class ExactGachaCalculatorTest {

  private final ExactGachaCalculator exact = new ExactGachaCalculator();

  static final PityRules TOY = new PityRules(0.1, 5, 0.1, 10, 0.5, true);

  @Test
  void alwaysFiveStarGivesHalfThenOne() {
    PityRules always = new PityRules(1.0, 1, 0.0, 1, 0.5, true);
    assertThat(exact.probabilityWithin(always, GachaState.FRESH, 1)).isCloseTo(0.5, within(1e-12));
    assertThat(exact.probabilityWithin(always, GachaState.FRESH, 2)).isCloseTo(1.0, within(1e-12));
  }

  @Test
  void zeroPullsGiveZero() {
    assertThat(exact.probabilityWithin(TOY, GachaState.FRESH, 0)).isZero();
  }

  @Test
  void expectedPullsMatchesClosedFormForSimpleRules() {
    // 毎回 100% で最高レア・ピックアップ 50%・すり抜け後確定 → 期待値 1.5 回
    PityRules always = new PityRules(1.0, 1, 0.0, 1, 0.5, true);
    assertThat(exact.expectedPulls(always, GachaState.FRESH, 10, 1e-12))
        .isCloseTo(1.5, within(1e-12));
  }

  @Test
  void expectedPullsFailsWhenNotConverged() {
    PityRules noGuarantee = new PityRules(0.01, 90, 0.0, 90, 0.5, false);
    assertThatThrownBy(() -> exact.expectedPulls(noGuarantee, GachaState.FRESH, 10, 1e-12))
        .isInstanceOf(IllegalStateException.class);
  }

  @Test
  void invalidArgumentsAreRejected() {
    assertThatThrownBy(() -> new PityRules(1.5, 1, 0, 1, 0.5, true))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new PityRules(0.1, 0, 0, 1, 0.5, true))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new PityRules(0.1, 1, 0, 0, 0.5, true))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new PityRules(Double.NaN, 1, 0, 1, 0.5, true))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> TOY.fiveStarRate(11)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new GachaState(-1, false))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> exact.probabilityWithin(TOY, new GachaState(10, false), 1))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> exact.probabilityWithin(TOY, GachaState.FRESH, -1))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Provide
  Arbitrary<PityRules> rules() {
    Arbitrary<Integer> hard = Arbitraries.integers().between(1, 90);
    return hard.flatMap(
        h ->
            Combinators.combine(
                    Arbitraries.doubles().between(0.0, 1.0),
                    Arbitraries.integers().between(1, h),
                    Arbitraries.doubles().between(0.0, 0.2),
                    Arbitraries.doubles().between(0.0, 1.0),
                    Arbitraries.of(true, false))
                .as(
                    (base, soft, inc, featured, guarantee) ->
                        new PityRules(base, soft, inc, h, featured, guarantee)));
  }

  @Property(tries = 200)
  void cumulativeIsAProbabilityAndMonotonic(@ForAll("rules") PityRules rules) {
    double[] c = exact.cumulative(rules, GachaState.FRESH, 2 * rules.hardPity() + 5);
    for (int n = 0; n < c.length; n++) {
      assertThat(c[n]).isBetween(0.0, 1.0);
      if (n > 0) {
        assertThat(c[n]).isGreaterThanOrEqualTo(c[n - 1] - 1e-15);
      }
    }
  }

  @Property(tries = 200)
  void twoHardPitiesGuaranteeTheFeaturedWhenLossIsGuaranteed(@ForAll("rules") PityRules rules) {
    PityRules guaranteed =
        new PityRules(
            rules.baseRate(),
            rules.softPityStart(),
            rules.softPityIncrement(),
            rules.hardPity(),
            rules.featuredRate(),
            true);
    assertThat(exact.probabilityWithin(guaranteed, GachaState.FRESH, 2 * rules.hardPity()))
        .isCloseTo(1.0, within(1e-9));
  }

  @Property(tries = 200)
  void hardPityAlwaysGivesFiveStar(@ForAll("rules") PityRules rules) {
    assertThat(rules.fiveStarRate(rules.hardPity())).isEqualTo(1.0);
  }
}
