package dev.echolab.app;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.echolab.app.data.DataException;
import dev.echolab.app.tool.Arguments;
import dev.echolab.app.tool.ToolException;
import dev.echolab.app.tool.ToolHandler;
import io.modelcontextprotocol.server.McpServerFeatures.SyncToolSpecification;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.Tool;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * {@link ToolHandler} を MCP のツール定義に変換する。
 *
 * <p>入力の誤りやデータの不備は {@code isError: true} の結果として返し、サーバのプロセスは止めない。 結果のテキスト内容は契約どおりの JSON 1
 * オブジェクト（ADR-0008）。
 */
public final class McpToolAdapter {

  private static final Logger LOG = LoggerFactory.getLogger(McpToolAdapter.class);
  private static final ObjectMapper MAPPER = new ObjectMapper();
  private static final TypeReference<Map<String, Object>> MAP = new TypeReference<>() {};

  private McpToolAdapter() {}

  /** MCP のツール定義（名前は wire 名）と、呼び出しの処理。 */
  public static SyncToolSpecification specification(ToolHandler handler) {
    Tool tool =
        Tool.builder(handler.wireName(), MAPPER.convertValue(handler.inputSchema(), MAP))
            .description(handler.description())
            .build();
    return SyncToolSpecification.builder()
        .tool(tool)
        .callHandler((exchange, request) -> invoke(handler, request.arguments()))
        .build();
  }

  /** ツールを呼び、結果を MCP の形にする。例外は外に出さない。 */
  public static CallToolResult invoke(ToolHandler handler, Map<String, Object> arguments) {
    try {
      String json = handler.call(Arguments.of(arguments)).toJson();
      return CallToolResult.builder().addTextContent(json).isError(false).build();
    } catch (ToolException | DataException | IllegalArgumentException | ArithmeticException e) {
      return error(handler.wireName() + ": " + e.getMessage());
    } catch (RuntimeException e) {
      // 想定外の失敗。詳細は標準エラーのログに残し、LLM には要点だけを返す
      LOG.error("ツール {} の実行に失敗しました", handler.wireName(), e);
      return error(
          handler.wireName() + ": 計算中に予期しないエラーが発生しました（" + e.getClass().getSimpleName() + "）");
    }
  }

  private static CallToolResult error(String message) {
    return CallToolResult.builder().addTextContent(message).isError(true).build();
  }
}
