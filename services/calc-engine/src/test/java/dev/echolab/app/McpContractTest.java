package dev.echolab.app;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.ToolEnvelope;
import dev.echolab.app.tool.ToolHandler;
import dev.echolab.calc.golden.GoldenCase;
import dev.echolab.calc.golden.GoldenFile;
import dev.echolab.calc.golden.GoldenLoader;
import io.modelcontextprotocol.server.McpServerFeatures.SyncToolSpecification;
import io.modelcontextprotocol.spec.McpSchema.CallToolRequest;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.TextContent;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;

/** MCP の境界の形（ツール名・入力スキーマ・結果の JSON）の契約テスト（ADR-0008）。 */
class McpContractTest {

  private final McpToolConfiguration configuration = new McpToolConfiguration();
  private final List<ToolHandler> handlers =
      McpToolConfiguration.handlers(new DomainData(TestPaths.DATA_ROOT));

  @Test
  void toolsMatchDomainManifestWithWireNames() {
    Set<String> declared = new TreeSet<>();
    TestPaths.domainManifest().get("tools").forEach(t -> declared.add(t.get("name").asText()));
    Set<String> exposed = new TreeSet<>();
    handlers.forEach(h -> exposed.add(h.domainName()));
    assertThat(exposed).isEqualTo(declared);

    List<SyncToolSpecification> specs =
        configuration.mcpTools(configuration.toolHandlers(configuration.domainData()));
    assertThat(specs)
        .extracting(s -> s.tool().name())
        .containsExactly(
            "damage_expected", "echo_score", "gacha_probability_within", "gacha_simulate");
    specs.forEach(s -> assertThat(s.tool().name()).matches("^[a-zA-Z0-9_-]{1,64}$"));
    // 入力の検証はツール側が日本語で行う（SDK の英語の検証は切る）
    assertThat(configuration.toolInputValidatedByHandlers()).isNotNull();
  }

  @Test
  void inputSchemasDescribeEveryFieldAndAcceptGoldenInputs() {
    for (ToolHandler h : handlers) {
      JsonNode schema = h.inputSchema();
      assertThat(schema.get("type").asText()).as(h.wireName()).isEqualTo("object");
      assertThat(schema.get("additionalProperties").asBoolean(true)).as(h.wireName()).isFalse();
      assertThat(h.description()).as(h.wireName()).isNotBlank();
      JsonNode properties = schema.get("properties");
      properties
          .properties()
          .forEach(
              f ->
                  assertThat(f.getValue().path("description").asText())
                      .as("%s.%s の説明", h.wireName(), f.getKey())
                      .isNotBlank());
      schema
          .get("required")
          .forEach(r -> assertThat(properties.has(r.asText())).as(r.asText()).isTrue());
    }
    // ゴールデンケースの入力のキーは、すべてスキーマにある
    for (GoldenFile file : GoldenLoader.loadAll(TestPaths.GOLDEN_DIR)) {
      ToolHandler h = handler(file.tool());
      JsonNode properties = h.inputSchema().get("properties");
      for (GoldenCase c : file.cases()) {
        c.input()
            .fieldNames()
            .forEachRemaining(k -> assertThat(properties.has(k)).as("%s: %s", c.id(), k).isTrue());
      }
    }
  }

  @Test
  void callHandlerReturnsSingleJsonObjectAsText() {
    SyncToolSpecification spec = McpToolAdapter.specification(handler("gacha.probability_within"));
    Map<String, Object> args =
        TestPaths.args(
            "{\"rules\": {\"base_rate\": 0.1, \"soft_pity_start\": 5, \"soft_pity_increment\":"
                + " 0.1, \"hard_pity\": 10, \"featured_rate\": 0.5, \"guarantee_after_loss\":"
                + " true}, \"start_pity\": 8, \"guaranteed\": true, \"pulls\": 1}");
    @SuppressWarnings("unchecked")
    Map<String, Object> schemaProperties =
        (Map<String, Object>) spec.tool().inputSchema().get("properties");
    assertThat(schemaProperties).containsKey("banner");
    CallToolResult result =
        spec.callHandler()
            .apply(
                null, CallToolRequest.builder("gacha_probability_within").arguments(args).build());
    assertThat(result.isError()).isFalse();
    assertThat(result.content()).hasSize(1);
    JsonNode doc = TestPaths.json(((TextContent) result.content().get(0)).text());
    List<String> keys = new ArrayList<>();
    doc.fieldNames().forEachRemaining(keys::add);
    assertThat(keys).containsExactly("tool", "values", "unverified_inputs", "data_version");
    assertThat(doc.get("tool").asText()).isEqualTo("gacha.probability_within");
    assertThat(doc.get("values").get("probability").isTextual()).isTrue();
    assertThat(new BigDecimal(doc.get("values").get("probability").asText()))
        .isEqualByComparingTo("0.6");
    assertThat(doc.get("unverified_inputs").isArray()).isTrue();
    assertThat(doc.get("data_version").isNull()).isTrue();
  }

  @Test
  void envelopeSerializesValuesAsPlainDecimalStringsInOrder() {
    ToolEnvelope e =
        new ToolEnvelope(
            "damage.expected",
            new ToolEnvelope.Values()
                .put("total", new BigDecimal("1E+3").setScale(6))
                .put("probability", 1.0e-7)
                .put("zero", 0.0)
                .build(),
            List.of("gacha_rules:x"),
            "v2.x");
    assertThat(e.toJson())
        .isEqualTo(
            "{\"tool\":\"damage.expected\",\"values\":{\"total\":\"1000.000000\","
                + "\"probability\":\"0.00000010\",\"zero\":\"0.0\"},"
                + "\"unverified_inputs\":[\"gacha_rules:x\"],\"data_version\":\"v2.x\"}");
    assertThat(e.values()).containsOnlyKeys("total", "probability", "zero");
  }

  @Test
  void damageValuesFollowGoldenFieldOrder() {
    JsonNode input = GoldenLoader.loadAll(TestPaths.GOLDEN_DIR).get(0).cases().get(0).input();
    ToolEnvelope e = handler("damage.expected").call(dev.echolab.app.tool.Arguments.of(input));
    assertThat(e.values().keySet())
        .containsExactly(
            "base",
            "bonus_multiplier",
            "crit_multiplier",
            "defense_multiplier",
            "resistance_multiplier",
            "total");
    // 出力は Precision の桁（小数 6 桁）にそろう
    assertThat(e.values().get("total")).isEqualTo("6192.000000");
  }

  private ToolHandler handler(String domainName) {
    return handlers.stream()
        .filter(h -> h.domainName().equals(domainName))
        .findFirst()
        .orElseThrow();
  }
}
