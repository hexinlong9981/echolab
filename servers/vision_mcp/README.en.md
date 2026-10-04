# servers/vision_mcp — Screenshot reading (OCR)

[日本語](README.md) ｜ **English** ｜ [中文](README.zh-CN.md)

> This is a translation; the Japanese version is canonical.

An MCP server (stdio) that reads screenshots with OCR (Tesseract) and returns **only the numeric fields declared in a template** (M4, [ADR-0010](../../docs/adr/en/0010-screenshot-reading-and-injection-evals.md)).
It is domain-agnostic. Each domain pack's templates (`domains/<pack>/vision/*.yaml`) decide what to read,
and the gateway decides which tools may be used from the pack's `domain.yaml` (default-deny).

## How it works

1. Check the image path: a PNG or JPEG of at most 10 MB inside `ECHOLAB_VISION_ROOTS` (separated by `:`, default: the working directory). Symbolic links are resolved before the check.
2. Turn it into lines with Tesseract (`jpn+eng`, `--psm 6`).
3. A line becomes a value only when it has the form "label + number (+ `%`)" and the label, section and unit match a template field. Out-of-range values and duplicate fields are errors (a likely misread).
4. The result is the same `ToolEnvelope` JSON as calc-engine. `values` contains numbers only (the fields plus `lines_read` and `lines_ignored`).

**Text in the image never reaches the LLM.** Even if the image says "ignore the previous instructions…", that line matches no field and is dropped.
The values read become core source IDs (for example `c1.sub_crit_rate`), and answers cite them with placeholders.

## Usage

```bash
sudo dnf install tesseract tesseract-langpack-jpn      # Rocky Linux etc. (Ubuntu: apt-get install tesseract-ocr tesseract-ocr-jpn)
.venv/bin/pytest tests/test_vision.py                  # the real-OCR tests are skipped without Tesseract
```

| Environment variable | Default | Meaning |
|---|---|---|
| `ECHOLAB_VISION_ROOTS` | working directory | Where images may be read from |
| `ECHOLAB_VISION_TEMPLATES` | `domains/*/vision` | Where templates live |
| `ECHOLAB_TESSERACT` | `tesseract` | The OCR executable |

## Layout

| File | Contents |
|---|---|
| `ocr.py` | Calls Tesseract as a child process (no extra Python dependency) |
| `reader.py` | Loading templates, checking image paths, extracting fields from lines |
| `server.py` | The MCP server (one tool per template) |

The template format is checked against `tests/schemas/vision_template.schema.json`.
