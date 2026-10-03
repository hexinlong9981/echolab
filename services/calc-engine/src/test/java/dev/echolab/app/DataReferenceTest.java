package dev.echolab.app;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.app.data.DataException;
import dev.echolab.app.data.DataItem;
import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.Arguments;
import dev.echolab.app.tool.EchoScoreTool;
import dev.echolab.app.tool.GachaProbabilityWithinTool;
import dev.echolab.app.tool.GachaSimulateTool;
import dev.echolab.app.tool.ToolEnvelope;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** データを参照する入力（banner・profile・max_roll の省略）と、未確認データの記録（ADR-0006）。 */
class DataReferenceTest {

  private static final DomainData REPO_DATA = new DomainData(TestPaths.DATA_ROOT);

  /** echo-001 と同じ声骸。 */
  private static final String ECHO =
      """
      {"name": "sample-echo-a", "cost": 4, "main": {"stat": "CRIT_RATE", "value": 0.22},
       "subs": [{"stat": "CRIT_RATE", "value": 0.08}, {"stat": "CRIT_DMG", "value": 0.16},
                {"stat": "ATK_PERCENT", "value": 0.09}, {"stat": "ATK_FLAT", "value": 40},
                {"stat": "ENERGY_REGEN", "value": 0.06}]}
      """;

  private static final String WEIGHTS =
      "{\"CRIT_RATE\": 1.0, \"CRIT_DMG\": 1.0, \"ATK_PERCENT\": 0.75, \"ATK_FLAT\": 0.25,"
          + " \"ENERGY_REGEN\": 0.5}";

  private static final String MAX_ROLL =
      "{\"CRIT_RATE\": 0.1, \"CRIT_DMG\": 0.2, \"ATK_PERCENT\": 0.12, \"ATK_FLAT\": 60,"
          + " \"ENERGY_REGEN\": 0.12}";

  private static String dataVersion() {
    return TestPaths.domainManifest().get("data_version").asText();
  }

  @Test
  void bannerReferenceReadsRulesAndMarksThemUnverified() {
    ToolEnvelope e =
        new GachaProbabilityWithinTool(REPO_DATA)
            .call(
                Arguments.of(
                    TestPaths.args(
                        "{\"banner\": \"featured-character\", \"start_pity\": 0,"
                            + " \"guaranteed\": false, \"pulls\": 80}")));
    assertThat(e.tool()).isEqualTo("gacha.probability_within");
    // データの規則は golden の gacha-004 と同じ値（説明用の toy 規則）
    assertThat(Double.parseDouble(e.values().get("probability")))
        .isCloseTo(0.6058637851964593, org.assertj.core.api.Assertions.within(1e-12));
    assertThat(e.unverifiedInputs()).containsExactly("gacha_rules:featured-character");
    assertThat(e.dataVersion()).isEqualTo(dataVersion());
  }

  @Test
  void simulationAcceptsBannerReferenceToo() {
    ToolEnvelope e =
        new GachaSimulateTool(REPO_DATA)
            .call(
                Arguments.of(
                    TestPaths.args(
                        "{\"banner\": \"featured-character\", \"start_pity\": 0,"
                            + " \"guaranteed\": false, \"pulls\": 160, \"trials\": 1000}")));
    assertThat(e.values()).containsEntry("probability", "1.0").containsEntry("std_error", "0.0");
    assertThat(e.unverifiedInputs()).containsExactly("gacha_rules:featured-character");
    assertThat(e.dataVersion()).isEqualTo(dataVersion());
  }

  @Test
  void profileAndDefaultMaxRollAreBothRecorded() {
    ToolEnvelope e =
        new EchoScoreTool(REPO_DATA)
            .call(
                Arguments.of(
                    TestPaths.args(
                        "{\"echo\": " + ECHO + ", \"profile\": \"sample-crit-attacker\"}")));
    // 重み・最大値とも echo-001 と同じ値なので、期待値も同じ
    assertThat(e.values())
        .containsEntry("score", "2.579167")
        .containsEntry("percent_of_ideal", "73.690476");
    assertThat(e.unverifiedInputs())
        .containsExactly("echo_weights:max_roll", "echo_weights:sample-crit-attacker");
    assertThat(e.dataVersion()).isEqualTo(dataVersion());
  }

  @Test
  void explicitWeightsWithDefaultMaxRollRecordOnlyMaxRoll() {
    ToolEnvelope e =
        new EchoScoreTool(REPO_DATA)
            .call(
                Arguments.of(
                    TestPaths.args("{\"echo\": " + ECHO + ", \"weights\": " + WEIGHTS + "}")));
    assertThat(e.values()).containsEntry("score", "2.579167");
    assertThat(e.unverifiedInputs()).containsExactly("echo_weights:max_roll");
    assertThat(e.dataVersion()).isEqualTo(dataVersion());
  }

  @Test
  void profileWithExplicitMaxRollRecordsOnlyProfile() {
    ToolEnvelope e =
        new EchoScoreTool(REPO_DATA)
            .call(
                Arguments.of(
                    TestPaths.args(
                        "{\"echo\": "
                            + ECHO
                            + ", \"profile\": \"sample-crit-attacker\", \"max_roll\": "
                            + MAX_ROLL
                            + "}")));
    assertThat(e.unverifiedInputs()).containsExactly("echo_weights:sample-crit-attacker");
    assertThat(e.dataVersion()).isEqualTo(dataVersion());
  }

  @Test
  void dataDirectoryAndVersionComeFromDomainManifest(@TempDir Path root) throws IOException {
    // 版のディレクトリ名を決め打ちしていないことを、別の名前で確かめる
    Path data = writeDomain(root, "data/v9.z", "v9.z");
    Files.writeString(
        data.resolve("gacha_rules.yaml"),
        """
        schema_version: 1
        banners:
          - id: checked
            display_name: 確認済み
            verified: true
            source: "https://example.com"
            rules: { base_rate: 0.1, soft_pity_start: 100, soft_pity_increment: 0,
                     hard_pity: 100, featured_rate: 1.0, guarantee_after_loss: false }
        """);
    ToolEnvelope e =
        new GachaProbabilityWithinTool(new DomainData(root))
            .call(
                Arguments.of(
                    TestPaths.args(
                        "{\"banner\": \"checked\", \"start_pity\": 0, \"guaranteed\": false,"
                            + " \"pulls\": 10}")));
    assertThat(Double.parseDouble(e.values().get("probability")))
        .isCloseTo(0.6513215599, org.assertj.core.api.Assertions.within(1e-9));
    // 確認済みなら unverified_inputs は空だが、データを参照したので版は付く
    assertThat(e.unverifiedInputs()).isEmpty();
    assertThat(e.dataVersion()).isEqualTo("v9.z");
  }

  @Test
  void itemsWithoutVerifiedFlagAreTreatedAsUnverified(@TempDir Path root) throws IOException {
    Path data = writeDomain(root, "data", "v1");
    Files.writeString(
        data.resolve("echo_weights.yaml"),
        "max_roll: { values: { CRIT_RATE: 0.1 } }\nprofiles: []\n");
    DataItem item = new DomainData(root).maxRoll();
    assertThat(item.verified()).isFalse();
    assertThat(item.reference()).isEqualTo("echo_weights:max_roll");
  }

  @Test
  void unknownIdsAreRejected() {
    assertThatThrownBy(() -> REPO_DATA.banner("no-such-banner"))
        .isInstanceOf(DataException.class)
        .hasMessageContaining("no-such-banner")
        .hasMessageContaining("gacha_rules.yaml");
    assertThatThrownBy(() -> REPO_DATA.profile("no-such-profile"))
        .isInstanceOf(DataException.class)
        .hasMessageContaining("echo_weights.yaml");
  }

  @Test
  void brokenDataIsReportedNotCrashed(@TempDir Path root) throws IOException {
    DomainData data = new DomainData(root);
    // domain.yaml が無い
    assertThatThrownBy(data::maxRoll)
        .isInstanceOf(DataException.class)
        .hasMessageContaining("データファイルがありません");

    // data_dir が無い
    Files.createDirectories(root.resolve("wuwa"));
    Files.writeString(root.resolve("wuwa/domain.yaml"), "name: wuwa\n");
    assertThatThrownBy(data::maxRoll)
        .isInstanceOf(DataException.class)
        .hasMessageContaining("data_dir");

    Path dir = writeDomain(root, "data", "v1");
    // YAML として読めない
    Files.writeString(dir.resolve("echo_weights.yaml"), "max_roll: [unclosed\n");
    assertThatThrownBy(data::maxRoll)
        .isInstanceOf(DataException.class)
        .hasMessageContaining("読めません");
    // オブジェクトでない
    Files.writeString(dir.resolve("echo_weights.yaml"), "- a\n- b\n");
    assertThatThrownBy(data::maxRoll)
        .isInstanceOf(DataException.class)
        .hasMessageContaining("形式が不正");
    // max_roll が無い
    Files.writeString(dir.resolve("echo_weights.yaml"), "profiles: []\n");
    assertThatThrownBy(data::maxRoll)
        .isInstanceOf(DataException.class)
        .hasMessageContaining("max_roll がありません");
    // 中身（weights）が無い
    Files.writeString(
        dir.resolve("echo_weights.yaml"), "profiles:\n  - id: p\n    verified: false\n");
    assertThatThrownBy(() -> data.profile("p"))
        .isInstanceOf(DataException.class)
        .hasMessageContaining("weights がありません");
    // 一覧が無い
    Files.writeString(dir.resolve("gacha_rules.yaml"), "schema_version: 1\n");
    assertThatThrownBy(() -> data.banner("x")).isInstanceOf(DataException.class);
  }

  @Test
  void dataRootComesFromEnvironment() {
    assertThat(DomainData.fromEnvironment(Map.of()).domainDir())
        .isEqualTo(Path.of("domains", "wuwa"));
    assertThat(DomainData.fromEnvironment(Map.of(DomainData.DATA_ROOT_ENV, " ")).domainDir())
        .isEqualTo(Path.of("domains", "wuwa"));
    assertThat(DomainData.fromEnvironment(Map.of(DomainData.DATA_ROOT_ENV, "/srv/d")).domainDir())
        .isEqualTo(Path.of("/srv/d", "wuwa"));
  }

  @Test
  void invalidRulesInDataAreReportedWithTheirSource(@TempDir Path root) throws IOException {
    Path data = writeDomain(root, "data", "v1");
    Files.writeString(
        data.resolve("gacha_rules.yaml"),
        "banners:\n  - id: bad\n    verified: false\n    rules: { base_rate: 2 }\n");
    assertThatThrownBy(
            () ->
                new GachaProbabilityWithinTool(new DomainData(root))
                    .call(
                        Arguments.of(
                            TestPaths.args(
                                "{\"banner\": \"bad\", \"start_pity\": 0,"
                                    + " \"guaranteed\": false, \"pulls\": 1}"))))
        .hasMessageContaining("gacha_rules:bad.rules.");
  }

  @Test
  void dataItemCarriesFileIdAndBody() {
    DataItem item = REPO_DATA.banner("featured-character");
    JsonNode rules = item.body();
    assertThat(rules.get("hard_pity").asInt()).isPositive();
    assertThat(List.of(item.file(), item.id()))
        .containsExactly("gacha_rules", "featured-character");
  }

  private static Path writeDomain(Path root, String dataDir, String version) throws IOException {
    Path domain = Files.createDirectories(root.resolve("wuwa"));
    Files.writeString(
        domain.resolve("domain.yaml"),
        "name: wuwa\ndata_version: " + version + "\ndata_dir: " + dataDir + "\n");
    return Files.createDirectories(domain.resolve(dataDir));
  }
}
