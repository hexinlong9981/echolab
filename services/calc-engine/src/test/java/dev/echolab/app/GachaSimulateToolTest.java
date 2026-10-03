package dev.echolab.app;

import static org.assertj.core.api.Assertions.assertThat;

import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.Arguments;
import dev.echolab.app.tool.GachaSimulateTool;
import dev.echolab.app.tool.ToolEnvelope;
import org.junit.jupiter.api.Test;

/** gacha_simulate の既定値と、実行方式によらない再現性。 */
class GachaSimulateToolTest {

  private static final GachaSimulateTool TOOL =
      new GachaSimulateTool(new DomainData(TestPaths.DATA_ROOT));

  private static final String BASE =
      "{\"rules\": {\"base_rate\": 0.1, \"soft_pity_start\": 5, \"soft_pity_increment\": 0.1,"
          + " \"hard_pity\": 10, \"featured_rate\": 0.5, \"guarantee_after_loss\": true},"
          + " \"start_pity\": 0, \"guaranteed\": false, \"pulls\": 10";

  private static ToolEnvelope run(String extra) {
    return TOOL.call(Arguments.of(TestPaths.args(BASE + extra + "}")));
  }

  @Test
  void sameSeedGivesSameResultForEveryMethod() {
    ToolEnvelope sequential = run(", \"trials\": 30000, \"seed\": 7, \"method\": \"sequential\"");
    ToolEnvelope parallel =
        run(", \"trials\": 30000, \"seed\": 7, \"method\": \"parallel_stream\"");
    ToolEnvelope virtual = run(", \"trials\": 30000, \"seed\": 7, \"method\": \"virtual_threads\"");
    assertThat(parallel.values()).isEqualTo(sequential.values());
    assertThat(virtual.values()).isEqualTo(sequential.values());
    assertThat(sequential.values()).containsOnlyKeys("probability", "std_error");
  }

  @Test
  void defaultsAreSequentialSeedZeroAndDefaultTrials() {
    ToolEnvelope defaults = run("");
    ToolEnvelope explicit = run(", \"trials\": 100000, \"seed\": 0, \"method\": \"sequential\"");
    assertThat(defaults.values()).isEqualTo(explicit.values());
    double p = Double.parseDouble(defaults.values().get("probability"));
    double se = Double.parseDouble(defaults.values().get("std_error"));
    assertThat(se)
        .isCloseTo(Math.sqrt(p * (1 - p) / 100_000), org.assertj.core.api.Assertions.within(1e-15));
    assertThat(defaults.dataVersion()).isNull();
  }

  @Test
  void differentSeedsUsuallyDiffer() {
    assertThat(run(", \"trials\": 5000, \"seed\": 1").values())
        .isNotEqualTo(run(", \"trials\": 5000, \"seed\": 2").values());
  }
}
