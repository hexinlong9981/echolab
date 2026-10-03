package dev.echolab.app;

import dev.echolab.app.data.DomainData;
import dev.echolab.app.tool.DamageExpectedTool;
import dev.echolab.app.tool.EchoScoreTool;
import dev.echolab.app.tool.GachaProbabilityWithinTool;
import dev.echolab.app.tool.GachaSimulateTool;
import dev.echolab.app.tool.ToolHandler;
import io.modelcontextprotocol.server.McpServerFeatures.SyncToolSpecification;
import java.util.List;
import org.springframework.ai.mcp.customizer.McpSyncServerCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MCP で公開するツールの登録。Spring AI の MCP サーバの自動設定が {@link SyncToolSpecification} の一覧を拾う。
 *
 * <p>ツールの中身（{@link ToolHandler}）は Spring に依存しないので、ここは組み立てだけを行う。
 */
@Configuration(proxyBeanMethods = false)
public class McpToolConfiguration {

  /** データの参照先（環境変数 {@value DomainData#DATA_ROOT_ENV}）。 */
  @Bean
  public DomainData domainData() {
    return DomainData.fromEnvironment(System.getenv());
  }

  /** 公開するツール（domain.yaml の tools と同じ 4 つ）。 */
  @Bean
  public List<ToolHandler> toolHandlers(DomainData domainData) {
    return handlers(domainData);
  }

  /** MCP のツール定義。 */
  @Bean
  public List<SyncToolSpecification> mcpTools(List<ToolHandler> toolHandlers) {
    return toolHandlers.stream().map(McpToolAdapter::specification).toList();
  }

  /**
   * MCP の SDK による入力スキーマの検証を切る。
   *
   * <p>SDK の検証は英語のメッセージを返すため。入力の検証はツール側（{@code Arguments}・計算の各 record）が
   * スキーマと同じ条件（型・範囲・必須・未知のフィールド）で行い、どのフィールドが悪いかを日本語で返す。
   */
  @Bean
  public McpSyncServerCustomizer toolInputValidatedByHandlers() {
    return spec -> spec.validateToolInputs(false);
  }

  /** ツールの一覧を組み立てる（テストからも使う）。 */
  public static List<ToolHandler> handlers(DomainData data) {
    return List.of(
        new DamageExpectedTool(),
        new EchoScoreTool(data),
        new GachaProbabilityWithinTool(data),
        new GachaSimulateTool(data));
  }
}
