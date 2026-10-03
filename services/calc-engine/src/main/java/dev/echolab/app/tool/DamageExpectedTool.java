package dev.echolab.app.tool;

import dev.echolab.calc.damage.DamageBreakdown;
import dev.echolab.calc.damage.DamageCalculator;
import dev.echolab.calc.damage.DamageInput;
import dev.echolab.calc.domain.CharacterStats;
import dev.echolab.calc.domain.EnemyStats;
import java.util.Set;

/** {@code damage.expected}：期待ダメージと各乗区の明細。データは参照しない。 */
public final class DamageExpectedTool implements ToolHandler {

  private static final Set<String> FIELDS =
      Set.of(
          "atk",
          "skill_multiplier",
          "dmg_bonus",
          "crit_rate",
          "crit_dmg",
          "defense_constant",
          "enemy_def",
          "def_ignore",
          "enemy_res",
          "res_shred");

  private final DamageCalculator calculator = new DamageCalculator();

  @Override
  public String domainName() {
    return "damage.expected";
  }

  @Override
  public String description() {
    return "期待ダメージを計算し、基礎ダメージと各乗区（ダメージアップ・会心期待値・防御・耐性）の明細を返す。"
        + "入力はすべて呼び出し側が明示した数値で、ゲームの定数は埋め込んでいない。";
  }

  @Override
  public ToolEnvelope call(Arguments args) {
    args.requireOnly(FIELDS);
    DamageInput input =
        new DamageInput(
            new CharacterStats(
                args.decimal("atk"),
                args.decimal("crit_rate"),
                args.decimal("crit_dmg"),
                args.decimal("dmg_bonus")),
            args.decimal("skill_multiplier"),
            new EnemyStats(args.decimal("enemy_def"), args.decimal("enemy_res")),
            args.decimal("defense_constant"),
            args.decimal("def_ignore"),
            args.decimal("res_shred"));
    DamageBreakdown d = calculator.expected(input);
    ToolEnvelope.Values values =
        new ToolEnvelope.Values()
            .put("base", d.base())
            .put("bonus_multiplier", d.bonusMultiplier())
            .put("crit_multiplier", d.critMultiplier())
            .put("defense_multiplier", d.defenseMultiplier())
            .put("resistance_multiplier", d.resistanceMultiplier())
            .put("total", d.total());
    return new Provenance().envelope(domainName(), values.build());
  }
}
