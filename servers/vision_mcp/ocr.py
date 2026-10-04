"""Tesseract（OCR）で画像を行の列にする。

``tesseract`` の実行ファイルを子プロセスで呼ぶ（Python の追加の依存は無い）。
実行ファイルは環境変数 ``ECHOLAB_TESSERACT``（既定 ``tesseract``）で変えられる。
言語は日本語と英語（``jpn+eng``）、ページの分割は「一様な文字のかたまり」（``--psm 6``）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

LANGUAGES = "jpn+eng"
TIMEOUT_SECONDS = 20


class OcrError(RuntimeError):
    """OCR を実行できない、または失敗した。メッセージはそのまま利用者に見せる。"""


def tesseract_command() -> str:
    return os.environ.get("ECHOLAB_TESSERACT", "tesseract")


def available() -> bool:
    return shutil.which(tesseract_command()) is not None


def read_lines(image: Path) -> list[str]:
    """画像の文字を読み、空でない行の列を返す。"""
    command = tesseract_command()
    if shutil.which(command) is None:
        raise OcrError(
            f"OCR の実行ファイル {command} が見つかりません。"
            "Tesseract と日本語のデータを入れてください"
            "（例：dnf install tesseract tesseract-langpack-jpn、"
            "apt-get install tesseract-ocr tesseract-ocr-jpn）"
        )
    try:
        done = subprocess.run(
            [command, str(image), "stdout", "-l", LANGUAGES, "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise OcrError(f"OCR が {TIMEOUT_SECONDS} 秒以内に終わりませんでした") from e
    if done.returncode != 0:
        detail = done.stderr.strip().splitlines()[-1:] or ["（詳細なし）"]
        raise OcrError(f"OCR に失敗しました: {detail[0]}")
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]
