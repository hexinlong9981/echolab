package dev.echolab.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * calc-engine の MCP サーバ（stdio）。{@code java -jar calc-engine-mcp.jar} で起動する。
 *
 * <p>標準出力は MCP のプロトコルに使うので、バナーとログは出さない（ログは標準エラーへ。{@code logback-spring.xml}）。
 */
@SpringBootApplication
public class McpServerApplication {

  /** 起動する。 */
  public static void main(String[] args) {
    SpringApplication.run(McpServerApplication.class, args);
  }
}
