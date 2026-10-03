package dev.echolab.calc.golden;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Objects;

/**
 * ゴールデンケースのファイル 1 つ。
 *
 * @param schemaVersion ファイル形式の版
 * @param tool 対象のツール名（例 {@code damage.expected}）
 * @param cases ケースの一覧
 */
public record GoldenFile(
    @JsonProperty("schema_version") int schemaVersion, String tool, List<GoldenCase> cases) {

  /** 入力を検証し、ケースを不変リストにする。 */
  public GoldenFile {
    Objects.requireNonNull(tool, "tool");
    cases = List.copyOf(cases);
  }
}
