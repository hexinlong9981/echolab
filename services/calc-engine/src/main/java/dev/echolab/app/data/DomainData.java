package dev.echolab.app.data;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Objects;

/**
 * 鳴潮ドメインのデータ（ガチャ規則・声骸の重み）を読む。
 *
 * <p>場所は {@code <データの根>/wuwa/domain.yaml} の {@code data_dir} から決め、版のディレクトリ名（{@code v2.x}
 * など）をここに書かない。ファイルは呼び出しのたびに読み直す（小さく、サービスを状態なしに保てるため）。
 */
public final class DomainData {

  /** データの根を指定する環境変数。 */
  public static final String DATA_ROOT_ENV = "ECHOLAB_DATA_ROOT";

  /** 環境変数が無いときのデータの根（作業ディレクトリからの相対パス）。 */
  public static final String DEFAULT_DATA_ROOT = "domains";

  /** このサービスが扱うドメイン。 */
  public static final String DOMAIN = "wuwa";

  private static final String GACHA_RULES = "gacha_rules";
  private static final String ECHO_WEIGHTS = "echo_weights";

  private static final ObjectMapper YAML = new ObjectMapper(new YAMLFactory());

  private final Path domainDir;

  /**
   * データの根を指定して作る。
   *
   * @param dataRoot ドメインのディレクトリを並べた場所（例 {@code domains}）
   */
  public DomainData(Path dataRoot) {
    this.domainDir = Objects.requireNonNull(dataRoot, "dataRoot").resolve(DOMAIN);
  }

  /** 環境変数 {@value #DATA_ROOT_ENV} から作る（無ければ {@value #DEFAULT_DATA_ROOT}）。 */
  public static DomainData fromEnvironment(Map<String, String> env) {
    String root = env.get(DATA_ROOT_ENV);
    return new DomainData(Path.of(root == null || root.isBlank() ? DEFAULT_DATA_ROOT : root));
  }

  /** ドメインのディレクトリ（{@code <データの根>/wuwa}）。 */
  public Path domainDir() {
    return domainDir;
  }

  /** ガチャのバナー（{@code gacha_rules.yaml} の {@code banners[]}）。中身は {@code rules}。 */
  public DataItem banner(String id) {
    return findById(GACHA_RULES, "banners", "rules", id, "banner");
  }

  /** 声骸の重みのプロファイル（{@code echo_weights.yaml} の {@code profiles[]}）。中身は {@code weights}。 */
  public DataItem profile(String id) {
    return findById(ECHO_WEIGHTS, "profiles", "weights", id, "profile");
  }

  /** サブ詞条 1 枠の最大値（{@code echo_weights.yaml} の {@code max_roll}）。中身は {@code values}。 */
  public DataItem maxRoll() {
    Manifest manifest = manifest();
    JsonNode doc = read(manifest, ECHO_WEIGHTS);
    JsonNode item = doc.get("max_roll");
    if (item == null || !item.isObject()) {
      throw new DataException(ECHO_WEIGHTS + ".yaml に max_roll がありません");
    }
    return item(manifest, ECHO_WEIGHTS, "max_roll", item, "values");
  }

  private DataItem findById(
      String file, String listField, String bodyField, String id, String inputName) {
    Manifest manifest = manifest();
    JsonNode doc = read(manifest, file);
    JsonNode list = doc.get(listField);
    if (list != null && list.isArray()) {
      for (JsonNode item : list) {
        if (id.equals(item.path("id").asText(null))) {
          return item(manifest, file, id, item, bodyField);
        }
      }
    }
    throw new DataException(
        inputName + " '" + id + "' は " + file + ".yaml の " + listField + " にありません");
  }

  private static DataItem item(
      Manifest manifest, String file, String id, JsonNode item, String bodyField) {
    JsonNode body = item.get(bodyField);
    if (body == null || !body.isObject()) {
      throw new DataException(file + ".yaml の " + id + " に " + bodyField + " がありません");
    }
    // verified が無い・真偽値でない項目は未確認として扱う（安全側）
    boolean verified = item.path("verified").asBoolean(false);
    return new DataItem(file, id, verified, body, manifest.dataVersion());
  }

  /** {@code domain.yaml} のうち、データの場所と版。 */
  private record Manifest(Path dataDir, String dataVersion) {}

  private Manifest manifest() {
    JsonNode doc = readYaml(domainDir.resolve("domain.yaml"));
    String dataDir = doc.path("data_dir").asText("");
    String dataVersion = doc.path("data_version").asText("");
    if (dataDir.isBlank() || dataVersion.isBlank()) {
      throw new DataException(
          "domain.yaml に data_dir と data_version が必要です: " + domainDir.resolve("domain.yaml"));
    }
    return new Manifest(domainDir.resolve(dataDir), dataVersion);
  }

  private static JsonNode read(Manifest manifest, String file) {
    return readYaml(manifest.dataDir().resolve(file + ".yaml"));
  }

  private static JsonNode readYaml(Path file) {
    if (!Files.isRegularFile(file)) {
      throw new DataException("データファイルがありません: " + file.toAbsolutePath().normalize());
    }
    try {
      JsonNode doc = YAML.readTree(file.toFile());
      if (doc == null || !doc.isObject()) {
        throw new DataException("データファイルの形式が不正です: " + file);
      }
      return doc;
    } catch (IOException e) {
      throw new DataException("データファイルを読めません: " + file, e);
    }
  }
}
