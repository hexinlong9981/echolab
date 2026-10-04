"""OCR の行から、テンプレートで宣言した数値の項目だけを取り出す（ADR-0010）。

テンプレート（``domains/<パック>/vision/*.yaml``）の例::

    schema_version: 1
    tool: echo.read_screenshot
    description: 声骸の画面のスクリーンショットから、COST とメイン・サブ詞条の値を読む
    sections:
      - {name: main, header: メイン}
      - {name: sub, header: サブ}
    fields:
      - {name: cost, label: COST, unit: number, min: 1, max: 4}
      - {name: sub_crit_rate, section: sub, label: 会心率, unit: percent, min: 0, max: 1}

- 1 行が「ラベル + 数値（+ ``%``）」の形で、ラベル・見出しの区間・単位がすべて合うときだけ読む。
  それ以外の行（説明文・画像に書き込まれた指示など）は捨て、結果に文字列は一切入れない。
- ``unit: percent`` は ``%`` 付きの値を 100 で割る。``unit: number`` は ``%`` の無い値。
- 範囲（``min``・``max``）の外の値、同じ項目が 2 回読めたときは誤り（読み違いの疑い）にする。
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

#: 読み込む画像の拡張子と大きさの上限。
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024

_LINE = re.compile(r"^(?P<label>.*?)(?P<number>[0-9]+(?:\.[0-9]+)?)(?P<percent>%?)$")


class ReadError(ValueError):
    """画像を読めない、または読んだ値がテンプレートに合わない。メッセージは利用者に見せる。"""


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    unit: str  # percent / number
    section: str | None = None
    min: Decimal | None = None
    max: Decimal | None = None


@dataclass(frozen=True)
class Template:
    tool: str
    description: str
    sections: Mapping[str, str]  # 見出し → 区間の名前
    fields: tuple[Field, ...]

    @staticmethod
    def from_doc(doc: Mapping[str, Any]) -> Template:
        def dec(v: Any) -> Decimal | None:
            return None if v is None else Decimal(str(v))

        return Template(
            tool=str(doc["tool"]),
            description=str(doc["description"]),
            sections={_squash(s["header"]): s["name"] for s in doc.get("sections") or ()},
            fields=tuple(
                Field(
                    name=f["name"],
                    label=_squash(f["label"]),
                    unit=f["unit"],
                    section=f.get("section"),
                    min=dec(f.get("min")),
                    max=dec(f.get("max")),
                )
                for f in doc["fields"]
            ),
        )


def load_templates(dirs: Iterable[Path]) -> dict[str, Template]:
    """ディレクトリの ``*.yaml`` をすべて読む。ツール名 → テンプレート。"""
    templates: dict[str, Template] = {}
    for d in dirs:
        for path in sorted(Path(d).glob("*.yaml")):
            template = Template.from_doc(yaml.safe_load(path.read_text(encoding="utf-8")))
            if template.tool in templates:
                raise ValueError(f"ツール {template.tool} のテンプレートが重複しています: {path}")
            templates[template.tool] = template
    return templates


def template_dirs(cwd: Path) -> list[Path]:
    """テンプレートの置き場所。環境変数 ``ECHOLAB_VISION_TEMPLATES``（区切りは ``os.pathsep``）、
    無ければ ``domains/*/vision``。"""
    configured = os.environ.get("ECHOLAB_VISION_TEMPLATES")
    if configured:
        return [cwd / p for p in configured.split(os.pathsep) if p]
    return sorted(p for p in (cwd / "domains").glob("*/vision") if p.is_dir())


def resolve_image(path_text: str, *, cwd: Path) -> Path:
    """読んでよい画像のパスに直す。

    許可するのは ``ECHOLAB_VISION_ROOTS``（区切りは ``os.pathsep``、既定は作業ディレクトリ）の
    中にある PNG・JPEG だけ。シンボリックリンクは解決してから確かめる。
    """
    roots_text = os.environ.get("ECHOLAB_VISION_ROOTS")
    roots = [Path(r) for r in roots_text.split(os.pathsep) if r] if roots_text else [cwd]
    roots = [(r if r.is_absolute() else cwd / r).resolve() for r in roots]
    candidate = Path(path_text)
    image = (candidate if candidate.is_absolute() else cwd / candidate).resolve()
    if not any(image.is_relative_to(root) for root in roots):
        shown = "、".join(str(r) for r in roots)
        raise ReadError(
            f"このパスの画像は読めません（読める場所: {shown}。"
            "環境変数 ECHOLAB_VISION_ROOTS で変えられます）"
        )
    if image.suffix.lower() not in IMAGE_SUFFIXES:
        raise ReadError(f"PNG か JPEG の画像を指定してください: {candidate.name}")
    if not image.is_file():
        raise ReadError(f"画像が見つかりません: {path_text}")
    if image.stat().st_size > MAX_IMAGE_BYTES:
        raise ReadError(f"画像が大きすぎます（上限 {MAX_IMAGE_BYTES // (1024 * 1024)} MB）")
    return image


def extract(template: Template, lines: Sequence[str]) -> dict[str, Decimal]:
    """OCR の行から、テンプレートの項目を取り出す。

    結果は項目の値に加えて ``lines_read``（読んだ行の数）と ``lines_ignored``
    （項目にも見出しにも当たらず捨てた行の数）。どちらも数値だけで、行の文字列は返さない。
    """
    values: dict[str, Decimal] = {}
    section: str | None = None
    ignored = 0
    for raw in lines:
        line = _squash(raw)
        if line in template.sections:
            section = template.sections[line]
            continue
        hit = _match(template, line, section)
        if hit is None:
            ignored += 1
            continue
        field, value = hit
        if field.name in values:
            raise ReadError(f"同じ項目（{field.name}）が 2 回読めました。画像を確かめてください")
        values[field.name] = value
    if not values:
        raise ReadError(
            "テンプレートに合う項目を 1 つも読めませんでした。対象の画面か確かめてください"
        )
    values["lines_read"] = Decimal(len(lines))
    values["lines_ignored"] = Decimal(ignored)
    return values


def _match(template: Template, line: str, section: str | None) -> tuple[Field, Decimal] | None:
    m = _LINE.match(line)
    if m is None:
        return None
    percent = m.group("percent") == "%"
    for field in template.fields:
        if field.label != m.group("label"):
            continue
        if field.section is not None and field.section != section:
            continue
        if (field.unit == "percent") != percent:
            continue
        value = Decimal(m.group("number"))
        if percent:
            value /= 100
        if (field.min is not None and value < field.min) or (
            field.max is not None and value > field.max
        ):
            raise ReadError(
                f"{field.name} の値 {m.group('number')}{m.group('percent')} が範囲の外です"
                "（読み違いの疑い）。画像を確かめてください"
            )
        return field, value
    return None


def _squash(text: str) -> str:
    """全角・半角をそろえ（NFKC）、空白を除く。OCR が入れる余分な空白を無視するため。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
