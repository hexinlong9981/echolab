package dev.echolab.app.tool;

/**
 * ツールが入力を拒否した、またはデータを読めずに計算できなかったことを表す。
 *
 * <p>MCP では {@code isError: true} の結果として返し、サーバは止めない。メッセージはそのまま LLM と利用者に見えるので、 何が悪いかが分かる日本語で書く。
 */
public final class ToolException extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** メッセージだけの例外。 */
  public ToolException(String message) {
    super(message);
  }

  /** 原因付きの例外。 */
  public ToolException(String message, Throwable cause) {
    super(message, cause);
  }
}
