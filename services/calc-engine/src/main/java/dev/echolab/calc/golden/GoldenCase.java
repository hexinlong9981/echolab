package dev.echolab.calc.golden;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.util.Objects;

/**
 * ゴールデンケース 1 件。Java の契約テストと Python の評価で同じファイルを使う。
 *
 * @param id ケース ID
 * @param description 説明
 * @param derivation 期待値の出どころ（手計算・閉じた式・参照実装）
 * @param input 入力（ツールごとの形）
 * @param expected 期待値（ツールごとの形）
 * @param tolerance 許容誤差（絶対値）
 */
public record GoldenCase(
    String id,
    String description,
    Derivation derivation,
    JsonNode input,
    JsonNode expected,
    double tolerance) {

  /** 入力を検証する。 */
  public GoldenCase {
    Objects.requireNonNull(id, "id");
    Objects.requireNonNull(derivation, "derivation");
    Objects.requireNonNull(input, "input");
    Objects.requireNonNull(expected, "expected");
    if (tolerance < 0) {
      throw new IllegalArgumentException("tolerance は 0 以上である必要があります: " + tolerance);
    }
  }

  /** 入力の数値を BigDecimal で取り出す（文字列表現を経由して誤差を持ち込まない）。 */
  public BigDecimal inputDecimal(String field) {
    return decimal(input, field);
  }

  /** 期待値の数値を BigDecimal で取り出す。 */
  public BigDecimal expectedDecimal(String field) {
    return decimal(expected, field);
  }

  /** {@code node} の {@code field} を BigDecimal で取り出す。 */
  public static BigDecimal decimal(JsonNode node, String field) {
    JsonNode value = node.get(field);
    if (value == null || !value.isNumber()) {
      throw new IllegalArgumentException("数値のフィールドがありません: " + field);
    }
    return new BigDecimal(value.asText());
  }
}
