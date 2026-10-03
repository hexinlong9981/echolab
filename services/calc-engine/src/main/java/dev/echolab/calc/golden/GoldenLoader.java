package dev.echolab.calc.golden;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;

/** YAML のゴールデンケースを読み込む。未知のキーは誤記とみなして失敗させる。 */
public final class GoldenLoader {

  /** サポートするファイル形式の版。 */
  public static final int SUPPORTED_SCHEMA_VERSION = 1;

  private static final ObjectMapper MAPPER =
      new ObjectMapper(new YAMLFactory())
          .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
          .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);

  private GoldenLoader() {}

  /** ファイルを 1 つ読み込む。 */
  public static GoldenFile load(Path file) {
    try {
      GoldenFile golden = MAPPER.readValue(file.toFile(), GoldenFile.class);
      if (golden.schemaVersion() != SUPPORTED_SCHEMA_VERSION) {
        throw new IllegalArgumentException(
            "未対応の schema_version です: " + golden.schemaVersion() + " (" + file + ")");
      }
      return golden;
    } catch (IOException e) {
      throw new UncheckedIOException("ゴールデンケースを読めません: " + file, e);
    }
  }

  /** ディレクトリ直下の {@code *.yaml} をファイル名順にすべて読み込む。 */
  public static List<GoldenFile> loadAll(Path dir) {
    try (Stream<Path> files = Files.list(dir)) {
      return files
          .filter(p -> p.getFileName().toString().endsWith(".yaml"))
          .sorted()
          .map(GoldenLoader::load)
          .toList();
    } catch (IOException e) {
      throw new UncheckedIOException("ディレクトリを読めません: " + dir, e);
    }
  }
}
