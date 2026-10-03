package dev.echolab.app.tool;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * ツールの結果（ADR-0008 の契約。Python 側は {@code core/contracts.py} の {@code ToolEnvelope}）。
 *
 * <p>JSON の例:
 *
 * <pre>{@code
 * {"tool": "gacha.probability_within",
 *  "values": {"probability": "0.6058637851964593"},
 *  "unverified_inputs": ["gacha_rules:featured-character"],
 *  "data_version": "v2.x"}
 * }</pre>
 *
 * @param tool ドメインのツール名（{@code .} 区切り。例 {@code damage.expected}）
 * @param values フィールド名 → 10 進数の文字列（{@link BigDecimal#toPlainString()}）。順序を保つ
 * @param unverifiedInputs 計算に使った未確認データの ID（{@code <データファイル名>:<項目 ID>}。整列・重複なし）
 * @param dataVersion 参照したデータの版。データを参照しなかった場合は null
 */
public record ToolEnvelope(
    String tool, Map<String, String> values, List<String> unverifiedInputs, String dataVersion) {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  /** 入力を検証し、不変にする（values は順序を保つ）。 */
  public ToolEnvelope {
    Objects.requireNonNull(tool, "tool");
    values = Collections.unmodifiableMap(new LinkedHashMap<>(values));
    unverifiedInputs = List.copyOf(unverifiedInputs);
  }

  /** 契約どおりの JSON 文字列（MCP のテキスト内容として返す）。 */
  public String toJson() {
    ObjectNode root = MAPPER.createObjectNode();
    root.put("tool", tool);
    ObjectNode v = root.putObject("values");
    values.forEach(v::put);
    ArrayNode u = root.putArray("unverified_inputs");
    unverifiedInputs.forEach(u::add);
    if (dataVersion == null) {
      root.putNull("data_version");
    } else {
      root.put("data_version", dataVersion);
    }
    try {
      return MAPPER.writeValueAsString(root);
    } catch (JsonProcessingException e) {
      throw new IllegalStateException("結果を JSON にできません", e);
    }
  }

  /** 結果の値を組み立てる（順序を保つ）。 */
  public static final class Values {
    private final Map<String, String> map = new LinkedHashMap<>();

    /** {@link BigDecimal} の値を追加する（呼び出し側で出力用に丸めておく）。 */
    public Values put(String field, BigDecimal value) {
      map.put(field, value.toPlainString());
      return this;
    }

    /** 確率など {@code double} の値を追加する（{@link BigDecimal#valueOf(double)} の最短表現）。 */
    public Values put(String field, double value) {
      return put(field, BigDecimal.valueOf(value));
    }

    /** 組み立てた値。 */
    public Map<String, String> build() {
      return map;
    }
  }
}
