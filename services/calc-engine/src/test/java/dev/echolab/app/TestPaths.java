package dev.echolab.app;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.util.Map;

/** テストで使うリポジトリ内の場所と、JSON の変換。 */
public final class TestPaths {

  /** ゴールデンケースのディレクトリ（{@code domains/wuwa/golden}。build.gradle.kts が渡す）。 */
  public static final Path GOLDEN_DIR = Path.of(System.getProperty("golden.dir", "missing"));

  /** データの根（{@code domains}）。 */
  public static final Path DATA_ROOT = GOLDEN_DIR.resolve("../..").normalize();

  private static final ObjectMapper JSON = new ObjectMapper();
  private static final ObjectMapper YAML = new ObjectMapper(new YAMLFactory());

  private TestPaths() {}

  /** {@code domains/wuwa/domain.yaml}。 */
  public static JsonNode domainManifest() {
    try {
      return YAML.readTree(DATA_ROOT.resolve("wuwa/domain.yaml").toFile());
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  /**
   * JSON のノードを、MCP の SDK が渡すのと同じ形の {@code Map} にする。
   *
   * <p>いったん JSON の文字列にしてから読み直すので、数値は MCP 経由と同じく {@code Double}・{@code Integer} になる。
   */
  public static Map<String, Object> asMcpArguments(JsonNode node) {
    try {
      return JSON.readValue(JSON.writeValueAsString(node), new TypeReference<>() {});
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  /** JSON の文字列から MCP の {@code arguments} を作る。 */
  public static Map<String, Object> args(String json) {
    try {
      return asMcpArguments(JSON.readTree(json));
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  /** JSON の文字列を読む。 */
  public static JsonNode json(String text) {
    try {
      return JSON.readTree(text);
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }
}
