# prompts/

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

*This is a translation; the Japanese version is canonical.*

Prompts for the Wuthering Waves domain pack.

| File | Contents |
|---|---|
| `system.md` | The domain system prompt. It is appended after the core rules (`core/agent/prompts/core.md`: numbers come from tools; answers are placeholder templates) |

Policy:

- Prompts contain no numbers (multipliers, probabilities, etc.). Numbers are always taken from tool results (ADR-0001).
- How numbers are handled (citing source IDs, compare tools) is written in the core rules; this directory contains only the domain context (which tool to use when, terminology, data references).
- Prompts are version-controlled, and every change must pass the evals (`python -m core.evals`).
