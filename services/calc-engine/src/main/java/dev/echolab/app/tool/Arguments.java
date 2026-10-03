package dev.echolab.app.tool;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * ツールの入力（JSON のオブジェクト）を型付きで取り出す。
 *
 * <p>誤りはすべて {@link ToolException} にし、どのフィールドが悪いかをメッセージに含める（例 {@code rules.base_rate}）。
 * 数値は文字列表現を経由して {@link BigDecimal} にし、浮動小数点の誤差を持ち込まない。
 */
public final class Arguments {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private final ObjectNode node;
  private final String path;

  private Arguments(ObjectNode node, String path) {
    this.node = node;
    this.path = path;
  }

  /** MCP の {@code arguments}（null は空のオブジェクトとみなす）から作る。 */
  public static Arguments of(Map<String, Object> arguments) {
    if (arguments == null) {
      return new Arguments(JsonNodeFactory.instance.objectNode(), "");
    }
    JsonNode tree = MAPPER.valueToTree(arguments);
    return of(tree);
  }

  /** JSON のノードから作る。オブジェクト以外は拒否する。 */
  public static Arguments of(JsonNode node) {
    return wrap(node, "");
  }

  /**
   * JSON のノードから作る。エラーメッセージではフィールド名の前に {@code path} を付ける。
   *
   * @param path 出どころ（例 {@code gacha_rules:featured-character.rules}）
   */
  public static Arguments of(JsonNode node, String path) {
    return wrap(node, path);
  }

  private static Arguments wrap(JsonNode node, String path) {
    if (node == null || !node.isObject()) {
      throw new ToolException(label(path, "入力") + " は JSON のオブジェクトである必要があります");
    }
    return new Arguments((ObjectNode) node, path);
  }

  /** 元の JSON（読み取り専用として扱う）。 */
  public JsonNode json() {
    return node;
  }

  /** フィールドがあるか（null は無いものとみなす）。 */
  public boolean has(String field) {
    JsonNode value = node.get(field);
    return value != null && !value.isNull();
  }

  /** 許されていないフィールドがあれば拒否する（誤記を黙って無視しない）。 */
  public Arguments requireOnly(Set<String> allowed) {
    Set<String> unknown = new TreeSet<>();
    node.fieldNames().forEachRemaining(unknown::add);
    unknown.removeAll(allowed);
    if (!unknown.isEmpty()) {
      throw new ToolException(label(path, "入力") + " に未知のフィールドがあります: " + String.join(", ", unknown));
    }
    return this;
  }

  /** 2 つのうちちょうど 1 つだけが与えられていることを確かめ、与えられた方の名前を返す。 */
  public String requireExactlyOne(String first, String second) {
    boolean a = has(first);
    boolean b = has(second);
    if (a == b) {
      throw new ToolException(qualified(first) + " と " + qualified(second) + " のどちらか一方だけを指定してください");
    }
    return a ? first : second;
  }

  /** 必須の数値。 */
  public BigDecimal decimal(String field) {
    JsonNode value = require(field);
    if (!value.isNumber()) {
      throw new ToolException(qualified(field) + " は数値である必要があります");
    }
    if ((value.isDouble() || value.isFloat()) && !Double.isFinite(value.doubleValue())) {
      throw new ToolException(qualified(field) + " は有限の数値である必要があります");
    }
    return new BigDecimal(value.asText());
  }

  /** 必須の数値で、{@code [min, max]} の範囲にあるもの。 */
  public BigDecimal decimal(String field, BigDecimal min, BigDecimal max) {
    BigDecimal value = decimal(field);
    if (value.compareTo(min) < 0 || value.compareTo(max) > 0) {
      throw new ToolException(
          qualified(field)
              + " は "
              + min.toPlainString()
              + "〜"
              + max.toPlainString()
              + " である必要があります: "
              + value.toPlainString());
    }
    return value;
  }

  /** 必須の整数で、{@code [min, max]} の範囲にあるもの。 */
  public long integer(String field, long min, long max) {
    BigDecimal value = decimal(field);
    long result;
    try {
      result = value.longValueExact();
    } catch (ArithmeticException e) {
      throw new ToolException(qualified(field) + " は整数である必要があります: " + value.toPlainString(), e);
    }
    if (result < min || result > max) {
      throw new ToolException(
          qualified(field) + " は " + min + "〜" + max + " である必要があります: " + result);
    }
    return result;
  }

  /** 必須の整数（{@code int} の範囲）で、{@code [min, max]} の範囲にあるもの。 */
  public int intValue(String field, int min, int max) {
    return Math.toIntExact(integer(field, min, max));
  }

  /** 必須の真偽値。 */
  public boolean bool(String field) {
    JsonNode value = require(field);
    if (!value.isBoolean()) {
      throw new ToolException(qualified(field) + " は true か false である必要があります");
    }
    return value.booleanValue();
  }

  /** 必須の文字列（空は不可）。 */
  public String string(String field) {
    JsonNode value = require(field);
    if (!value.isTextual() || value.textValue().isBlank()) {
      throw new ToolException(qualified(field) + " は空でない文字列である必要があります");
    }
    return value.textValue();
  }

  /** 必須のオブジェクト。 */
  public Arguments object(String field) {
    return wrap(require(field), qualified(field));
  }

  /** 必須の配列。要素はオブジェクトとして取り出す。 */
  public List<Arguments> objects(String field) {
    JsonNode value = require(field);
    if (!value.isArray()) {
      throw new ToolException(qualified(field) + " は配列である必要があります");
    }
    List<Arguments> items = new ArrayList<>(value.size());
    for (int i = 0; i < value.size(); i++) {
      items.add(wrap(value.get(i), qualified(field) + "[" + i + "]"));
    }
    return List.copyOf(items);
  }

  /** このオブジェクトのフィールド名（入力の順）。 */
  public List<String> fieldNames() {
    List<String> names = new ArrayList<>();
    node.fieldNames().forEachRemaining(names::add);
    return List.copyOf(names);
  }

  /** エラーメッセージ用の、入力全体から見たフィールド名。 */
  public String qualified(String field) {
    return path.isEmpty() ? field : path + "." + field;
  }

  private JsonNode require(String field) {
    if (!has(field)) {
      throw new ToolException(qualified(field) + " は必須です");
    }
    return node.get(field);
  }

  private static String label(String path, String fallback) {
    return path.isEmpty() ? fallback : path;
  }
}
