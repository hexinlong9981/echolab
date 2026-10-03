/**
 * calc-engine を MCP サーバ（Spring Boot + Spring AI、stdio）として公開する層（ADR-0004・ADR-0008）。
 *
 * <p>計算は {@code dev.echolab.calc} の公開 API を呼ぶだけで、ここには計算式を置かない。 逆向きの依存（計算パッケージから Spring やこの層への依存）は
 * ArchUnit で禁止している。
 */
package dev.echolab.app;
