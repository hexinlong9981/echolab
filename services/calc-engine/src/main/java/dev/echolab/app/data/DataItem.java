package dev.echolab.app.data;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Objects;

/**
 * データファイルから取り出した 1 項目と、その出どころ（ADR-0006）。
 *
 * @param file データファイル名（拡張子なし。例 {@code gacha_rules}）
 * @param id 項目 ID（例 {@code featured-character}・{@code max_roll}）
 * @param verified 出典を確認済みか（{@code verified: true}）
 * @param body 計算に使う中身（バナーの {@code rules}・プロファイルの {@code weights}・{@code max_roll.values}）
 * @param dataVersion データの版（{@code domain.yaml} の {@code data_version}）
 */
public record DataItem(
    String file, String id, boolean verified, JsonNode body, String dataVersion) {

  /** 入力を検証する。 */
  public DataItem {
    Objects.requireNonNull(file, "file");
    Objects.requireNonNull(id, "id");
    Objects.requireNonNull(body, "body");
    Objects.requireNonNull(dataVersion, "dataVersion");
  }

  /** 結果の {@code unverified_inputs} に載せる ID（{@code <データファイル名>:<項目 ID>}）。 */
  public String reference() {
    return file + ":" + id;
  }
}
