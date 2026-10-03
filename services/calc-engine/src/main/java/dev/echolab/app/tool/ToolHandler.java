package dev.echolab.app.tool;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;

/**
 * MCP で公開する 1 つのツール。Spring にも MCP の SDK にも依存しないので、テストでは直接呼べる。
 *
 * <p>入力の誤りは {@link ToolException}（または計算側の {@link IllegalArgumentException}）で知らせる。
 */
public interface ToolHandler {

  /** ドメインのツール名（{@code domain.yaml} の {@code tools[].name}。例 {@code damage.expected}）。 */
  String domainName();

  /** MCP・LLM に見せる名前（ADR-0008：{@code .} を {@code _} に替える）。 */
  default String wireName() {
    return domainName().replace('.', '_');
  }

  /** LLM に見せる説明。 */
  String description();

  /** 入力の JSON Schema（{@code src/main/resources/tools/<wire 名>.schema.json}）。 */
  default JsonNode inputSchema() {
    return Schemas.load(wireName());
  }

  /** ツールを実行する。 */
  ToolEnvelope call(Arguments arguments);

  /** 入力スキーマをクラスパスから読む。 */
  final class Schemas {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Schemas() {}

    static JsonNode load(String wireName) {
      String resource = "/tools/" + wireName + ".schema.json";
      try (InputStream in = ToolHandler.class.getResourceAsStream(resource)) {
        if (in == null) {
          throw new IllegalStateException("入力スキーマがありません: " + resource);
        }
        return MAPPER.readTree(in);
      } catch (IOException e) {
        throw new UncheckedIOException("入力スキーマを読めません: " + resource, e);
      }
    }
  }
}
