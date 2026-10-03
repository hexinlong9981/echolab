[日本語](../0004-M1ではSpringを導入しない.md) ｜ [English](../en/0004-no-spring-in-m1.md) ｜ **中文**

> 本文为译文，以日文版为准。

# ADR-0004：M1 不引入 Spring，作为纯 Java 库构建

- 状态：采纳
- 日期：2026-10-03

## 背景

计算服务最终会作为 MCP 服务器（Spring Boot + Spring AI 的 MCP Server）对外公开。
但 M1 的目的是确立“计算是正确的”。

## 决定

M1 的 `calc-engine` 作为不依赖 Spring 的纯库构建，作为 MCP 公开的层在 M2 中另行添加。

## 理由

1. **关注点分离**：将计算逻辑与框架分离，测试会更快更简单（M1 的全部测试无需启动 Spring 上下文即可运行）。
2. **依赖少**：M1 的生产依赖只有 YAML 读取（Jackson），即使严格设置构建与静态分析（Error Prone・`-Werror`）也易于维护。
3. **易于替换**：采用之后再添加公开层的形式，即使 MCP 的 SDK・Spring 的版本变化，也不会影响计算逻辑。
4. **Native Image**：不依赖框架的部分越大，使用 GraalVM Native Image 时越不容易出问题。

## 否决的方案

| 方案 | 否决的理由 |
|---|---|
| 从一开始就作为 Spring Boot 应用构建 | 会增加 M1 中用不到的依赖与配置，难以专注于计算的正确性 |

## 影响

- 在 M2 中添加 `app` 层（Spring Boot・MCP 工具定义），它只调用 `calc` 的公开 API。
- 在 M2 中用 ArchUnit 添加“计算包不依赖框架”的规则。
