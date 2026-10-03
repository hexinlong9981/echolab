package dev.echolab.calc.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.calc.damage.DamageBreakdown;
import dev.echolab.calc.damage.DamageCalculator;
import dev.echolab.calc.damage.DamageInput;
import dev.echolab.calc.domain.CharacterStats;
import dev.echolab.calc.domain.Echo;
import dev.echolab.calc.domain.EnemyStats;
import dev.echolab.calc.domain.MainAffix;
import dev.echolab.calc.domain.Stat;
import dev.echolab.calc.domain.SubAffix;
import dev.echolab.calc.echo.EchoScore;
import dev.echolab.calc.echo.EchoScorer;
import dev.echolab.calc.gacha.ExactGachaCalculator;
import dev.echolab.calc.gacha.GachaState;
import dev.echolab.calc.gacha.PityRules;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

/**
 * ゴールデンケース（domains/wuwa/golden/*.yaml）との契約テスト。
 *
 * <p>同じファイルを Python の評価でも使うので、ここが落ちたら Java・Python・YAML のどれかが食い違っている。
 */
class GoldenContractTest {

  private static final Path GOLDEN_DIR = Path.of(System.getProperty("golden.dir", "missing"));

  private static final Set<String> KNOWN_TOOLS =
      Set.of("damage.expected", "echo.score", "gacha.probability_within");

  @Test
  void goldenDirectoryExistsAndCoversEveryTool() {
    assertThat(GOLDEN_DIR).isDirectory();
    Set<String> tools =
        GoldenLoader.loadAll(GOLDEN_DIR).stream().map(GoldenFile::tool).collect(Collectors.toSet());
    assertThat(tools).isEqualTo(KNOWN_TOOLS);
  }

  /** 3 者の一致が実装どうしの合意だけにならないよう、参照実装以外の出どころを持つケースを各ツールに要求する。 */
  @Test
  void everyToolHasCaseAnchoredOutsideReferenceImplementation() {
    for (GoldenFile file : GoldenLoader.loadAll(GOLDEN_DIR)) {
      assertThat(file.cases())
          .as("%s に derivation が reference 以外のケースがない", file.tool())
          .anyMatch(c -> c.derivation() != Derivation.REFERENCE);
    }
  }

  @Test
  void derivationIsRequiredAndValidated() throws Exception {
    Path tmp = Files.createTempFile("golden", ".yaml");
    String header = "schema_version: 1\ntool: x\ncases:\n  - id: a\n";
    String body = "    input: {}\n    expected: {}\n    tolerance: 0\n";
    try {
      Files.writeString(tmp, header + "    derivation: closed_form\n" + body);
      assertThat(GoldenLoader.load(tmp).cases().get(0).derivation())
          .isEqualTo(Derivation.CLOSED_FORM);
      Files.writeString(tmp, header + body);
      org.assertj.core.api.Assertions.assertThatThrownBy(() -> GoldenLoader.load(tmp))
          .isInstanceOf(java.io.UncheckedIOException.class);
      Files.writeString(tmp, header + "    derivation: guess\n" + body);
      org.assertj.core.api.Assertions.assertThatThrownBy(() -> GoldenLoader.load(tmp))
          .isInstanceOf(java.io.UncheckedIOException.class);
    } finally {
      Files.deleteIfExists(tmp);
    }
  }

  @TestFactory
  Stream<DynamicTest> everyGoldenCaseMatches() {
    List<DynamicTest> tests = new ArrayList<>();
    for (GoldenFile file : GoldenLoader.loadAll(GOLDEN_DIR)) {
      assertThat(file.cases()).isNotEmpty();
      for (GoldenCase c : file.cases()) {
        tests.add(
            DynamicTest.dynamicTest(file.tool() + " / " + c.id(), () -> verify(file.tool(), c)));
      }
    }
    return tests.stream();
  }

  @Test
  void unknownKeysAreRejected() throws Exception {
    Path tmp = Files.createTempFile("golden", ".yaml");
    try {
      Files.writeString(tmp, "schema_version: 1\ntool: x\ncases: []\ntypo: 1\n");
      org.assertj.core.api.Assertions.assertThatThrownBy(() -> GoldenLoader.load(tmp))
          .isInstanceOf(java.io.UncheckedIOException.class);
      Files.writeString(tmp, "schema_version: 2\ntool: x\ncases: []\n");
      org.assertj.core.api.Assertions.assertThatThrownBy(() -> GoldenLoader.load(tmp))
          .isInstanceOf(IllegalArgumentException.class);
    } finally {
      Files.deleteIfExists(tmp);
    }
  }

  private static void verify(String tool, GoldenCase c) {
    switch (tool) {
      case "damage.expected" -> verifyDamage(c);
      case "echo.score" -> verifyEcho(c);
      case "gacha.probability_within" -> verifyGacha(c);
      default -> throw new AssertionError("未知のツール: " + tool);
    }
  }

  private static void verifyDamage(GoldenCase c) {
    DamageInput input =
        new DamageInput(
            new CharacterStats(
                c.inputDecimal("atk"),
                c.inputDecimal("crit_rate"),
                c.inputDecimal("crit_dmg"),
                c.inputDecimal("dmg_bonus")),
            c.inputDecimal("skill_multiplier"),
            new EnemyStats(c.inputDecimal("enemy_def"), c.inputDecimal("enemy_res")),
            c.inputDecimal("defense_constant"),
            c.inputDecimal("def_ignore"),
            c.inputDecimal("res_shred"));
    DamageBreakdown actual = new DamageCalculator().expected(input);
    Map<String, BigDecimal> map = actual.asMap();
    assertThat(map.keySet()).containsExactlyInAnyOrderElementsOf(fieldNames(c.expected()));
    map.forEach((k, v) -> assertClose(c, k, v.doubleValue()));
  }

  private static void verifyEcho(GoldenCase c) {
    JsonNode e = c.input().get("echo");
    List<SubAffix> subs = new ArrayList<>();
    e.get("subs").forEach(s -> subs.add(new SubAffix(stat(s), GoldenCase.decimal(s, "value"))));
    JsonNode main = e.get("main");
    Echo echo =
        new Echo(
            e.get("name").asText(),
            e.get("cost").asInt(),
            new MainAffix(stat(main), GoldenCase.decimal(main, "value")),
            subs);
    EchoScore s =
        new EchoScorer()
            .score(echo, statMap(c.input().get("weights")), statMap(c.input().get("max_roll")));
    assertClose(c, "score", s.score().doubleValue());
    assertClose(c, "percent_of_ideal", s.percentOfIdeal().doubleValue());
  }

  private static void verifyGacha(GoldenCase c) {
    JsonNode r = c.input().get("rules");
    PityRules rules =
        new PityRules(
            r.get("base_rate").asDouble(),
            r.get("soft_pity_start").asInt(),
            r.get("soft_pity_increment").asDouble(),
            r.get("hard_pity").asInt(),
            r.get("featured_rate").asDouble(),
            r.get("guarantee_after_loss").asBoolean());
    GachaState start =
        new GachaState(
            c.input().get("start_pity").asInt(), c.input().get("guaranteed").asBoolean());
    double p =
        new ExactGachaCalculator().probabilityWithin(rules, start, c.input().get("pulls").asInt());
    assertClose(c, "probability", p);
  }

  private static void assertClose(GoldenCase c, String field, double actual) {
    assertThat(actual)
        .as("%s.%s", c.id(), field)
        .isCloseTo(c.expectedDecimal(field).doubleValue(), within(c.tolerance()));
  }

  private static Stat stat(JsonNode node) {
    return Stat.valueOf(node.get("stat").asText());
  }

  private static Map<Stat, BigDecimal> statMap(JsonNode node) {
    Map<Stat, BigDecimal> map = new EnumMap<>(Stat.class);
    node.fieldNames().forEachRemaining(k -> map.put(Stat.valueOf(k), GoldenCase.decimal(node, k)));
    return map;
  }

  private static List<String> fieldNames(JsonNode node) {
    List<String> names = new ArrayList<>();
    node.fieldNames().forEachRemaining(names::add);
    return names;
  }
}
