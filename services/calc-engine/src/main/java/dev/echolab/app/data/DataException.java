package dev.echolab.app.data;

/** ドメインのデータ（{@code domains/<ドメイン>/data/...}）を読めない、または参照した ID が無い。 */
public final class DataException extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** メッセージだけの例外。 */
  public DataException(String message) {
    super(message);
  }

  /** 原因付きの例外。 */
  public DataException(String message, Throwable cause) {
    super(message, cause);
  }
}
