package dev.echolab.calc.damage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.echolab.calc.domain.CharacterStats;
import dev.echolab.calc.domain.EnemyStats;
import java.math.BigDecimal;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.constraints.BigRange;
import net.jqwik.api.constraints.Scale;
import org.junit.jupiter.api.Test;

class DamageCalculatorTest {

  private final DamageCalculator calculator = new DamageCalculator();

  private static BigDecimal d(String v) {
    return new BigDecimal(v);
  }

  private static DamageInput input(BigDecimal atk, BigDecimal critRate) {
    return new DamageInput(
        new CharacterStats(atk, critRate, d("2.0"), d("0.3")),
        d("2.0"),
        new EnemyStats(d("1000"), d("0.1")),
        d("1600"),
        BigDecimal.ZERO,
        BigDecimal.ZERO);
  }

  @Test
  void breakdownMultipliesToTotal() {
    DamageBreakdown b = calculator.expected(input(d("2000"), d("0.5")));
    BigDecimal product =
        b.base()
            .multiply(b.bonusMultiplier())
            .multiply(b.critMultiplier())
            .multiply(b.defenseMultiplier())
            .multiply(b.resistanceMultiplier());
    assertThat(product.doubleValue()).isCloseTo(b.total().doubleValue(), within(1e-2));
    assertThat(b.asMap()).containsKeys("base", "total").hasSize(6);
  }

  @Test
  void critRateAboveOneIsClamped() {
    assertThat(DamageCalculator.critMultiplier(d("1.5"), d("2.0"))).isEqualByComparingTo("2.0");
    assertThat(DamageCalculator.critMultiplier(d("-0.1"), d("2.0"))).isEqualByComparingTo("1");
  }

  @Test
  void negativeResistanceIsHalved() {
    assertThat(DamageCalculator.resistanceMultiplier(d("0.1"), d("0.3")))
        .isEqualByComparingTo("1.1");
  }

  @Test
  void resistanceOfOneOrMoreIsRejected() {
    assertThatThrownBy(() -> DamageCalculator.resistanceMultiplier(d("1.0"), BigDecimal.ZERO))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void invalidInputsAreRejected() {
    assertThatThrownBy(() -> new CharacterStats(d("-1"), d("0"), d("1.5"), d("0")))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new CharacterStats(d("1"), d("0"), d("0.5"), d("0")))
        .isInstanceOf(IllegalArgumentException.class);
    CharacterStats ok = new CharacterStats(d("1"), d("0"), d("1.5"), d("0"));
    EnemyStats enemy = new EnemyStats(d("0"), d("0"));
    assertThatThrownBy(() -> new DamageInput(ok, d("1"), enemy, d("0"), d("0"), d("0")))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new DamageInput(ok, d("1"), enemy, d("1"), d("1.5"), d("0")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Property
  void damageIsMonotonicInAttack(
      @ForAll @BigRange(min = "1", max = "100000") @Scale(2) BigDecimal atk,
      @ForAll @BigRange(min = "0", max = "1000") @Scale(2) BigDecimal extra,
      @ForAll @BigRange(min = "0", max = "1") @Scale(3) BigDecimal critRate) {
    BigDecimal low = calculator.expected(input(atk, critRate)).total();
    BigDecimal high = calculator.expected(input(atk.add(extra), critRate)).total();
    assertThat(high).isGreaterThanOrEqualTo(low);
  }

  @Property
  void defenseMultiplierIsBetweenZeroAndOne(
      @ForAll @BigRange(min = "1", max = "10000") BigDecimal constant,
      @ForAll @BigRange(min = "0", max = "100000") BigDecimal defense,
      @ForAll @BigRange(min = "0", max = "1") @Scale(2) BigDecimal ignore) {
    BigDecimal m = DamageCalculator.defenseMultiplier(constant, defense, ignore);
    assertThat(m).isGreaterThan(BigDecimal.ZERO).isLessThanOrEqualTo(BigDecimal.ONE);
  }

  private static org.assertj.core.data.Offset<Double> within(double v) {
    return org.assertj.core.data.Offset.offset(v);
  }
}
