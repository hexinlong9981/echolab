# servers/vision_mcp — 截图读取（OCR）

[日本語](README.md) ｜ [English](README.en.md) ｜ **中文**

> 本文为译文，以日文版为准。

用 OCR（Tesseract）读取截图，**只返回模板中声明的数值字段**的 MCP 服务器（stdio）（M4、[ADR-0010](../../docs/adr/zh-CN/0010-截图读取与注入评估.md)）。
它不依赖任何领域。读什么由各领域包的模板（`domains/<包>/vision/*.yaml`）决定，
能用哪些工具由网关根据领域包的 `domain.yaml` 声明决定（默认拒绝）。

## 工作方式

1. 检查图片路径：必须是 `ECHOLAB_VISION_ROOTS`（用 `:` 分隔，默认为工作目录）中的 PNG・JPEG，不超过 10 MB。符号链接先解析再检查。
2. 用 Tesseract（`jpn+eng`、`--psm 6`）转成文本行。
3. 只有当一行是"标签 + 数字（+ `%`）"的形式，且标签、所在区段、单位都与模板字段一致时，才作为值读取。超出范围的值、同一字段重复出现都视为错误（疑似误读）。
4. 结果是与 calc-engine 相同的 `ToolEnvelope` JSON。`values` 只有数值（各字段，以及 `lines_read`・`lines_ignored`）。

**图片里的文字不会传给 LLM。** 即使图片上写着"忽略之前的指示……"，那一行也对不上任何字段，会被丢弃。
读到的值成为核心的出处 ID（如 `c1.sub_crit_rate`），回答用占位符引用。

## 用法

```bash
sudo dnf install tesseract tesseract-langpack-jpn      # Rocky Linux 等（Ubuntu：apt-get install tesseract-ocr tesseract-ocr-jpn）
.venv/bin/pytest tests/test_vision.py                  # 没有 Tesseract 时跳过真实 OCR 的测试
```

| 环境变量 | 默认值 | 含义 |
|---|---|---|
| `ECHOLAB_VISION_ROOTS` | 工作目录 | 允许读取图片的位置 |
| `ECHOLAB_VISION_TEMPLATES` | `domains/*/vision` | 模板的位置 |
| `ECHOLAB_TESSERACT` | `tesseract` | OCR 的可执行文件 |

## 结构

| 文件 | 内容 |
|---|---|
| `ocr.py` | 以子进程调用 Tesseract（不增加 Python 依赖） |
| `reader.py` | 读取模板、检查图片路径、从文本行中取出字段 |
| `server.py` | MCP 服务器（每个模板一个工具） |

模板格式由 `tests/schemas/vision_template.schema.json` 检查。
