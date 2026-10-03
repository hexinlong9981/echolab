package dev.echolab.calc.golden;

import com.fasterxml.jackson.annotation.JsonProperty;

/** ゴールデンケースの期待値の出どころ。YAML では小文字の文字列で書く。 */
public enum Derivation {
  /** 手計算。 */
  @JsonProperty("hand")
  HAND,
  /** 解析的な閉じた式（例 {@code 1 − (1 − p)^n}）。 */
  @JsonProperty("closed_form")
  CLOSED_FORM,
  /** 参照実装（厳密解）で計算した値。実装どうしの照合だけでは独立した正解にならない。 */
  @JsonProperty("reference")
  REFERENCE
}
