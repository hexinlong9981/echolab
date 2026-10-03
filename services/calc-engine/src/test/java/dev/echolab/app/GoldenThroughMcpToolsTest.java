package dev.echolab.app;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.ToolHandler;
import dev.echolab.calc.golden.GoldenCase;
import dev.echolab.calc.golden.GoldenFile;
import dev.echolab.calc.golden.GoldenLoader;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.TextContent;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

/**
 * ゴールデンケースの入力を、そのまま MCP のツール（アダプタ経由）に渡して期待値と照合する（ADR-0008）。
 *
 * <p>入力は MCP の SDK が渡すのと同じ {@code Map}（数値は {@code Double}）にしてから渡す。
 */
class GoldenThroughMcpToolsTest {

  private static final Map<String, ToolHandler> HANDLERS =
      McpToolConfiguration.handlers(new DomainData(TestPaths.DATA_ROOT)).stream()
          .collect(Collectors.toMap(ToolHandler::domainName, Function.identity()));

  /** モンテカルロ法で照合するときの試行回数。 */
  private static final int SIMULATION_TRIALS = 200_000;

  @TestFactory
  Stream<DynamicTest> everyGoldenCaseMatchesThroughTheTool() {
    List<DynamicTest> tests = new ArrayList<>();
    for (GoldenFile file : GoldenLoader.loadAll(TestPaths.GOLDEN_DIR)) {
      for (GoldenCase c : file.cases()) {
        tests.add(
            DynamicTest.dynamicTest(
                file.tool() + " / " + c.id(), () -> verifyExact(file.tool(), c)));
      }
    }
    assertThat(tests).isNotEmpty();
    return tests.stream();
  }

  /** gacha.probability_within のケースは、モンテカルロ法（gacha.simulate）でも誤差の範囲で一致する。 */
  @TestFactory
  Stream<DynamicTest> gachaGoldenCasesAgreeWithSimulation() {
    GoldenFile gacha =
        GoldenLoader.loadAll(TestPaths.GOLDEN_DIR).stream()
            .filter(f -> f.tool().equals("gacha.probability_within"))
            .findFirst()
            .orElseThrow();
    return gacha.cases().stream()
        .map(c -> DynamicTest.dynamicTest("gacha.simulate / " + c.id(), () -> verifySimulated(c)));
  }

  private static void verifyExact(String tool, GoldenCase c) {
    JsonNode result = call(tool, TestPaths.asMcpArguments(c.input()));
    assertThat(result.get("tool").asText()).isEqualTo(tool);
    JsonNode values = result.get("values");
    List<String> expectedFields = new ArrayList<>();
    c.expected().fieldNames().forEachRemaining(expectedFields::add);
    List<String> actualFields = new ArrayList<>();
    values.fieldNames().forEachRemaining(actualFields::add);
    assertThat(actualFields).as(c.id()).containsExactlyInAnyOrderElementsOf(expectedFields);
    for (String field : expectedFields) {
      assertThat(values.get(field).isTextual()).as("%s.%s は文字列", c.id(), field).isTrue();
      BigDecimal actual = new BigDecimal(values.get(field).asText());
      assertThat(actual.doubleValue())
          .as("%s.%s", c.id(), field)
          .isCloseTo(c.expectedDecimal(field).doubleValue(), within(c.tolerance()));
    }
    // 値をすべて入力で与えたので、データは参照していない
    assertThat(result.get("unverified_inputs")).isEmpty();
    assertThat(result.get("data_version").isNull()).isTrue();
  }

  private static void verifySimulated(GoldenCase c) {
    Map<String, Object> args = TestPaths.asMcpArguments(c.input());
    args.put("trials", SIMULATION_TRIALS);
    args.put("seed", 20261003L);
    JsonNode values = call("gacha.simulate", args).get("values");
    double p = values.get("probability").asDouble();
    double stdError = values.get("std_error").asDouble();
    double expected = c.expectedDecimal("probability").doubleValue();
    // 標準誤差の 5 倍（確率が 0 や 1 で標準誤差が 0 なら完全一致）
    assertThat(p).as(c.id()).isCloseTo(expected, within(5 * stdError + 1e-12));
  }

  private static JsonNode call(String tool, Map<String, Object> args) {
    CallToolResult result = McpToolAdapter.invoke(HANDLERS.get(tool), args);
    String text = ((TextContent) result.content().get(0)).text();
    assertThat(result.isError()).as(text).isFalse();
    return TestPaths.json(text);
  }
}
