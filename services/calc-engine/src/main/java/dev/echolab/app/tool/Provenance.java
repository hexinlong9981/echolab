package dev.echolab.app.tool;

import com.fasterxml.jackson.databind.JsonNode;
import dev.echolab.app.data.DataItem;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * 1 回の呼び出しで参照したデータの記録（ADR-0006）。
 *
 * <p>未確認（{@code verified: false}）の項目を集め、結果の {@code unverified_inputs} と {@code data_version} にする。
 */
final class Provenance {

  private final Set<String> unverified = new TreeSet<>();
  private String dataVersion;

  /** データの項目を使ったことを記録し、その中身を返す。 */
  JsonNode use(DataItem item) {
    if (!item.verified()) {
      unverified.add(item.reference());
    }
    dataVersion = item.dataVersion();
    return item.body();
  }

  /** 記録をもとに結果を作る。 */
  ToolEnvelope envelope(String tool, Map<String, String> values) {
    return new ToolEnvelope(tool, values, List.copyOf(unverified), dataVersion);
  }
}
