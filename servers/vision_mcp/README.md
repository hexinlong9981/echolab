# servers/vision_mcp — スクリーンショットの読み取り（OCR）

**日本語** ｜ [English](README.en.md) ｜ [中文](README.zh-CN.md)

スクリーンショットを OCR（Tesseract）で読み、**テンプレートで宣言した数値の項目だけ**を返す MCP サーバ（stdio）です（M4・[ADR-0010](../../docs/adr/0010-スクリーンショットの読み取りと注入の評価.md)）。
ドメインに依存しません。何を読むかは各ドメインパックのテンプレート（`domains/<パック>/vision/*.yaml`）が決め、
どのツールを使えるかはパックの `domain.yaml` の宣言でゲートウェイが決めます（既定拒否）。

## 仕組み

1. 画像のパスを検査する：`ECHOLAB_VISION_ROOTS`（区切りは `:`、既定は作業ディレクトリ）の中の PNG・JPEG、10 MB まで。シンボリックリンクは解決してから確かめる。
2. Tesseract（`jpn+eng`、`--psm 6`）で行の列にする。
3. 1 行が「ラベル + 数値（+ `%`）」で、ラベル・見出しの区間・単位がテンプレートの項目と合うときだけ値にする。範囲の外の値・同じ項目の重複は誤り（読み違いの疑い）。
4. 結果は calc-engine と同じ `ToolEnvelope` の JSON。`values` は数値だけ（項目と、`lines_read`・`lines_ignored`）。

**画像の中の文字列は LLM に届きません。** 画像に「前の指示を無視して…」と書かれていても、その行は項目に当たらないので捨てられます。
読んだ値はコアの出典 ID（例 `c1.sub_crit_rate`）になり、回答はプレースホルダで引用します。

## 使い方

```bash
sudo dnf install tesseract tesseract-langpack-jpn      # Rocky Linux など（Ubuntu: apt-get install tesseract-ocr tesseract-ocr-jpn）
.venv/bin/pytest tests/test_vision.py                  # Tesseract が無ければ実物の OCR の試験は飛ばす
```

| 環境変数 | 既定 | 内容 |
|---|---|---|
| `ECHOLAB_VISION_ROOTS` | 作業ディレクトリ | 読んでよい画像の場所 |
| `ECHOLAB_VISION_TEMPLATES` | `domains/*/vision` | テンプレートの置き場所 |
| `ECHOLAB_TESSERACT` | `tesseract` | OCR の実行ファイル |

## 構成

| ファイル | 内容 |
|---|---|
| `ocr.py` | Tesseract を子プロセスで呼ぶ（Python の追加の依存なし） |
| `reader.py` | テンプレートの読み込み、画像のパスの検査、行からの取り出し |
| `server.py` | MCP サーバ（テンプレートごとに 1 ツール） |

テンプレートの形式は `tests/schemas/vision_template.schema.json` で検査します。
