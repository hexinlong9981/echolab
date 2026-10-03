package dev.echolab.app;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.Arguments;
import dev.echolab.app.tool.ToolEnvelope;
import dev.echolab.app.tool.ToolHandler;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.TextContent;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/** 不正な入力は isError の結果（日本語のメッセージ）になり、例外でサーバを止めない。 */
class ToolErrorTest {

  private static final Map<String, ToolHandler> HANDLERS =
      McpToolConfiguration.handlers(new DomainData(TestPaths.DATA_ROOT)).stream()
          .collect(Collectors.toMap(ToolHandler::wireName, Function.identity()));

  private static final String RULES =
      "\"rules\": {\"base_rate\": 0.1, \"soft_pity_start\": 5, \"soft_pity_increment\": 0.1,"
          + " \"hard_pity\": 10, \"featured_rate\": 0.5, \"guarantee_after_loss\": true}";

  private static final String GACHA = "{" + RULES + ", \"start_pity\": 0, \"guaranteed\": false";

  private static final String ECHO =
      "{\"name\": \"e\", \"cost\": 4, \"main\": {\"stat\": \"CRIT_RATE\", \"value\": 0.2},"
          + " \"subs\": [{\"stat\": \"CRIT_DMG\", \"value\": 0.1}]}";

  private static final String DAMAGE =
      "\"atk\": 2000, \"skill_multiplier\": 2.5, \"dmg_bonus\": 0.3, \"crit_rate\": 0.6,"
          + " \"defense_constant\": 1600, \"enemy_def\": 1000, \"def_ignore\": 0,"
          + " \"res_shred\": 0";

  @ParameterizedTest(name = "{0}: {2}")
  @CsvSource(
      delimiterString = " | ",
      textBlock =
          """
          gacha_probability_within | {"banner": "featured-character", "start_pity": 0, "guaranteed": false, "pulls": 1, RULES_PLACEHOLDER} | どちらか一方だけ
          gacha_probability_within | {"start_pity": 0, "guaranteed": false, "pulls": 1} | どちらか一方だけ
          gacha_probability_within | {"banner": "no-such", "start_pity": 0, "guaranteed": false, "pulls": 1} | no-such
          gacha_probability_within | GACHA_PLACEHOLDER} | pulls は必須です
          gacha_probability_within | GACHA_PLACEHOLDER, "pulls": 10001} | pulls は 0〜10000
          gacha_probability_within | GACHA_PLACEHOLDER, "pulls": 1.5} | pulls は整数
          gacha_probability_within | GACHA_PLACEHOLDER, "pulls": "10"} | pulls は数値
          gacha_probability_within | GACHA_PLACEHOLDER, "pulls": 1, "typo": 1} | 未知のフィールドがあります: typo
          gacha_probability_within | {"rules": 1, "start_pity": 0, "guaranteed": false, "pulls": 1} | rules は JSON のオブジェクト
          gacha_probability_within | {"rules": {"base_rate": 1.5}, "start_pity": 0, "guaranteed": false, "pulls": 1} | rules.base_rate は 0〜1
          gacha_probability_within | {"rules": {"base_rate": 0.1, "soft_pity_start": 5, "soft_pity_increment": 0.1, "hard_pity": 10, "featured_rate": 0.5, "guarantee_after_loss": "yes"}, "start_pity": 0, "guaranteed": false, "pulls": 1} | guarantee_after_loss は true か false
          gacha_probability_within | {"rules": {"base_rate": 0.1, "soft_pity_start": 11, "soft_pity_increment": 0.1, "hard_pity": 10, "featured_rate": 0.5, "guarantee_after_loss": true}, "start_pity": 0, "guaranteed": false, "pulls": 1} | softPityStart
          gacha_probability_within | {RULES_PLACEHOLDER, "start_pity": 10, "guaranteed": false, "pulls": 1} | hardPity 未満
          gacha_probability_within | {"banner": "", "start_pity": 0, "guaranteed": false, "pulls": 1} | banner は空でない文字列
          gacha_probability_within | {"banner": 3, "start_pity": 0, "guaranteed": false, "pulls": 1} | banner は空でない文字列
          gacha_simulate | GACHA_PLACEHOLDER, "pulls": 1, "trials": 0} | trials は 1〜1000000
          gacha_simulate | GACHA_PLACEHOLDER, "pulls": 1, "trials": 1000001} | trials は 1〜1000000
          gacha_simulate | GACHA_PLACEHOLDER, "pulls": 1, "method": "gpu"} | method は sequential
          gacha_simulate | GACHA_PLACEHOLDER, "pulls": 1, "seed": 1e30} | seed は整数
          echo_score | {"echo": ECHO_PLACEHOLDER} | weights と profile のどちらか一方だけ
          echo_score | {"echo": ECHO_PLACEHOLDER, "weights": {"CRIT_DMG": 1}, "profile": "sample-crit-attacker"} | weights と profile のどちらか一方だけ
          echo_score | {"echo": ECHO_PLACEHOLDER, "profile": "no-such-profile"} | no-such-profile
          echo_score | {"echo": ECHO_PLACEHOLDER, "weights": {"LUCK": 1}} | weights.LUCK は未知のステータス
          echo_score | {"echo": ECHO_PLACEHOLDER, "weights": {"CRIT_DMG": -1}} | weights.CRIT_DMG は 0 以上
          echo_score | {"echo": ECHO_PLACEHOLDER, "weights": {"CRIT_DMG": 1}, "max_roll": {"CRIT_RATE": 0.1}} | maxRoll に正の値がありません
          echo_score | {"echo": {"name": "e", "cost": 5, "main": {"stat": "CRIT_RATE", "value": 0.2}, "subs": []}, "weights": {}} | echo.cost は 1〜4
          echo_score | {"echo": {"name": "e", "cost": 4, "main": {"stat": "LUCK", "value": 0.2}, "subs": []}, "weights": {}} | echo.main.stat の値
          echo_score | {"echo": {"name": "e", "cost": 4, "main": {"stat": "CRIT_RATE", "value": 0.2}, "subs": {}}, "weights": {}} | echo.subs は配列
          echo_score | {"echo": {"name": "e", "cost": 4, "main": {"stat": "CRIT_RATE", "value": 0.2}, "subs": [1]}, "weights": {}} | echo.subs[0] は JSON のオブジェクト
          echo_score | {"echo": {"name": "e", "cost": 4, "main": {"stat": "CRIT_RATE", "value": 0.2}, "subs": [{"stat": "CRIT_DMG", "value": -0.1}]}, "weights": {}} | echo.subs[0].value は 0 以上
          echo_score | {"echo": {"name": "e", "cost": 4, "main": {"stat": "CRIT_RATE", "value": 0.2}, "subs": [{"stat": "CRIT_DMG", "value": 0.1, "roll": 1}]}, "weights": {}} | echo.subs[0] に未知のフィールド
          damage_expected | {DAMAGE_PLACEHOLDER, "crit_dmg": 0.5, "enemy_res": 0.1} | critDmg は 1 以上
          damage_expected | {DAMAGE_PLACEHOLDER, "crit_dmg": 2.0, "enemy_res": 1.5} | 有効耐性は 1 未満
          damage_expected | {DAMAGE_PLACEHOLDER, "crit_dmg": 2.0} | enemy_res は必須です
          damage_expected | {DAMAGE_PLACEHOLDER, "crit_dmg": 2.0, "enemy_res": null} | enemy_res は必須です
          """)
  void invalidInputBecomesErrorResult(String tool, String json, String message) {
    String body =
        json.replace("RULES_PLACEHOLDER", RULES)
            .replace("GACHA_PLACEHOLDER", GACHA)
            .replace("ECHO_PLACEHOLDER", ECHO)
            .replace("DAMAGE_PLACEHOLDER", DAMAGE);
    CallToolResult result = McpToolAdapter.invoke(HANDLERS.get(tool), TestPaths.args(body));
    String text = text(result);
    assertThat(result.isError()).as(text).isTrue();
    assertThat(text).startsWith(tool + ": ").contains(message);
  }

  @Test
  void validCounterpartOfTheDamageCasesSucceeds() {
    // 上の damage_expected のケースは、この正しい入力から 1 か所だけ変えたもの
    CallToolResult result =
        McpToolAdapter.invoke(
            HANDLERS.get("damage_expected"),
            TestPaths.args("{" + DAMAGE + ", \"crit_dmg\": 2.0, \"enemy_res\": 0.1}"));
    assertThat(result.isError()).as(text(result)).isFalse();
  }

  @Test
  void nullArgumentsAreTreatedAsEmpty() {
    CallToolResult result = McpToolAdapter.invoke(HANDLERS.get("damage_expected"), null);
    assertThat(result.isError()).isTrue();
    assertThat(text(result)).contains("必須です");
  }

  @Test
  void nonFiniteNumbersAreRejected() {
    Map<String, Object> args = TestPaths.args("{\"atk\": 1}");
    args.put("atk", Double.NaN);
    CallToolResult result = McpToolAdapter.invoke(HANDLERS.get("damage_expected"), args);
    assertThat(result.isError()).isTrue();
    assertThat(text(result)).contains("atk は有限の数値");
  }

  @Test
  void topLevelMustBeAnObject() {
    JsonNode array = TestPaths.json("[1]");
    org.assertj.core.api.Assertions.assertThatThrownBy(() -> Arguments.of(array))
        .hasMessageContaining("入力 は JSON のオブジェクト");
  }

  @Test
  void unexpectedFailureIsReportedWithoutDetailsAndDoesNotEscape() {
    ToolHandler broken =
        new ToolHandler() {
          @Override
          public String domainName() {
            return "broken.tool";
          }

          @Override
          public String description() {
            return "常に失敗する";
          }

          @Override
          public ToolEnvelope call(Arguments arguments) {
            throw new IllegalStateException("内部の詳細");
          }
        };
    CallToolResult result = McpToolAdapter.invoke(broken, Map.of());
    assertThat(result.isError()).isTrue();
    assertThat(text(result)).isEqualTo("broken_tool: 計算中に予期しないエラーが発生しました（IllegalStateException）");
  }

  private static String text(CallToolResult result) {
    assertThat(result.content()).hasSize(1);
    return ((TextContent) result.content().get(0)).text();
  }
}
