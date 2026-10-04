"""スクリーンショットの読み取り（servers/vision_mcp、ADR-0010）の試験。

- テンプレートによる取り出しは、OCR の記録（evals/redteam/screenshots/*.ocr.txt）で試す。
  Tesseract は要らない。
- 実物の OCR と MCP サーバは Tesseract が要る。無ければ飛ばす
  （CI では ECHOLAB_OCR_REQUIRED=1 で、飛ばさずに失敗させる）。
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from servers.vision_mcp import ocr
from servers.vision_mcp.reader import ReadError, Template, extract, load_templates, resolve_image

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "evals/redteam/screenshots"
SCHEMA = json.loads((ROOT / "tests/schemas/vision_template.schema.json").read_text("utf-8"))

TEMPLATE_DOC = {
    "schema_version": 1,
    "tool": "demo.read_card",
    "description": "試験用のカード",
    "sections": [{"name": "main", "header": "メイン"}, {"name": "sub", "header": "サブ"}],
    "fields": [
        {"name": "cost", "label": "COST", "unit": "number", "min": 1, "max": 4},
        {
            "name": "main_crit_rate",
            "section": "main",
            "label": "会心率",
            "unit": "percent",
            "min": 0,
            "max": 1,
        },
        {
            "name": "sub_crit_rate",
            "section": "sub",
            "label": "会心率",
            "unit": "percent",
            "min": 0,
            "max": 1,
        },
        {
            "name": "sub_crit_dmg",
            "section": "sub",
            "label": "会心ダメージ",
            "unit": "percent",
            "min": 0,
            "max": 1,
        },
        {
            "name": "sub_atk_percent",
            "section": "sub",
            "label": "攻撃力",
            "unit": "percent",
            "min": 0,
            "max": 1,
        },
        {
            "name": "sub_atk_flat",
            "section": "sub",
            "label": "攻撃力",
            "unit": "number",
            "min": 0,
            "max": 1000,
        },
        {
            "name": "sub_energy_regen",
            "section": "sub",
            "label": "共鳴効率",
            "unit": "percent",
            "min": 0,
            "max": 1,
        },
    ],
}
TEMPLATE = Template.from_doc(TEMPLATE_DOC)
CLEAN = {
    "cost": Decimal(4),
    "main_crit_rate": Decimal("0.22"),
    "sub_crit_rate": Decimal("0.08"),
    "sub_crit_dmg": Decimal("0.16"),
    "sub_atk_percent": Decimal("0.09"),
    "sub_atk_flat": Decimal(40),
    "sub_energy_regen": Decimal("0.06"),
}
REQUIRED = os.environ.get("ECHOLAB_OCR_REQUIRED") == "1"
needs_ocr = pytest.mark.skipif(
    not ocr.available() and not REQUIRED, reason="Tesseract が無い（CI では必須）"
)


def recorded(name: str) -> list[str]:
    return (SHOTS / f"{name}.ocr.txt").read_text(encoding="utf-8").splitlines()


def fields(values: dict[str, Decimal]) -> dict[str, Decimal]:
    return {k: v for k, v in values.items() if not k.startswith("lines_")}


def test_templates_match_the_schema() -> None:
    validator = Draft202012Validator(SCHEMA)
    docs = [TEMPLATE_DOC] + [
        yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in sorted(ROOT.glob("domains/*/vision/*.yaml"))
    ]
    for doc in docs:
        assert [e.message for e in validator.iter_errors(doc)] == [], doc["tool"]


def test_clean_screenshot_yields_the_declared_fields() -> None:
    values = extract(TEMPLATE, recorded("echo-clean"))
    assert fields(values) == CLEAN
    assert values["lines_read"] == 10 and values["lines_ignored"] == 1  # 題名の行だけ捨てる


@pytest.mark.parametrize("name", ["echo-injection", "echo-injection-label"])
def test_injected_text_is_dropped_and_never_returned(name: str) -> None:
    values = extract(TEMPLATE, recorded(name))
    assert fields(values) == CLEAN  # 指示の行は項目にならない
    assert values["lines_ignored"] == 3
    assert all(isinstance(v, Decimal) for v in values.values())  # 結果に文字列は無い


def test_out_of_range_value_is_an_error() -> None:
    with pytest.raises(ReadError, match=r"sub_crit_dmg の値 500\.0% が範囲の外"):
        extract(TEMPLATE, recorded("echo-out-of-range"))


def test_unrelated_screenshot_is_an_error() -> None:
    with pytest.raises(ReadError, match="1 つも読めませんでした"):
        extract(TEMPLATE, recorded("not-an-echo"))


def test_duplicate_field_is_an_error() -> None:
    with pytest.raises(ReadError, match="2 回読めました"):
        extract(TEMPLATE, ["サブ", "会心率 8.0%", "会心率 9.0%"])


def test_sections_and_units_decide_the_field() -> None:
    values = extract(TEMPLATE, ["メイン", "会心率 22%", "サブ", "会心率 ８．０％", "攻撃力 40"])
    assert fields(values) == {
        "main_crit_rate": Decimal("0.22"),
        "sub_crit_rate": Decimal("0.08"),  # 全角も読む（NFKC）
        "sub_atk_flat": Decimal(40),
    }
    with pytest.raises(ReadError):  # 見出しの前は区間の外なので、どの項目にも当たらない
        extract(TEMPLATE, ["会心率 22%"])


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/etc/passwd", "このパスの画像は読めません"),
        ("../../etc/hostname.png", "このパスの画像は読めません"),
        ("evals/redteam/screenshots/echo-clean.ocr.txt", "PNG か JPEG"),
        ("evals/redteam/screenshots/nope.png", "画像が見つかりません"),
    ],
)
def test_image_paths_are_restricted(path: str, message: str) -> None:
    with pytest.raises(ReadError, match=message):
        resolve_image(path, cwd=ROOT)


def test_allowed_roots_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLAB_VISION_ROOTS", "tests")
    with pytest.raises(ReadError, match="このパスの画像は読めません"):
        resolve_image("evals/redteam/screenshots/echo-clean.png", cwd=ROOT)
    monkeypatch.setenv("ECHOLAB_VISION_ROOTS", os.pathsep.join(["tests", "evals/redteam"]))
    assert resolve_image("evals/redteam/screenshots/echo-clean.png", cwd=ROOT).is_file()


def test_symlink_out_of_the_root_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "inside").mkdir()
    (tmp_path / "secret.png").write_bytes(b"x")
    (tmp_path / "inside/link.png").symlink_to(tmp_path / "secret.png")
    with pytest.raises(ReadError, match="このパスの画像は読めません"):
        resolve_image("link.png", cwd=tmp_path / "inside")


def test_duplicate_template_tools_are_rejected(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(TEMPLATE_DOC), encoding="utf-8")
    with pytest.raises(ValueError, match="重複"):
        load_templates([tmp_path])


# ---------------------------------------------------------------------------
# 実物の OCR（Tesseract）
# ---------------------------------------------------------------------------


@needs_ocr
@pytest.mark.parametrize("name", ["echo-clean", "echo-injection", "echo-injection-label"])
def test_real_ocr_reads_the_synthetic_screenshots(name: str) -> None:
    assert fields(extract(TEMPLATE, ocr.read_lines(SHOTS / f"{name}.png"))) == CLEAN


@needs_ocr
async def test_mcp_server_returns_numbers_only(tmp_path: Path) -> None:
    from core.contracts import ToolError
    from core.gateway import McpStdioBackend

    (tmp_path / "demo.yaml").write_text(yaml.safe_dump(TEMPLATE_DOC), encoding="utf-8")
    backend = McpStdioBackend(
        [sys.executable, "-m", "servers.vision_mcp"],
        cwd=ROOT,
        env={"ECHOLAB_VISION_TEMPLATES": str(tmp_path)},
    )
    async with backend:
        [spec] = await backend.list_tools()
        assert spec.name == "demo_read_card" and spec.input_schema["required"] == ["image"]
        envelope = await backend.call_tool(
            "demo_read_card", {"image": "evals/redteam/screenshots/echo-injection.png"}
        )
        assert envelope.tool == "demo.read_card"
        assert fields(dict(envelope.values)) == CLEAN
        assert envelope.unverified_inputs == ()
        with pytest.raises(ToolError, match="このパスの画像は読めません"):
            await backend.call_tool("demo_read_card", {"image": "/etc/passwd"})
        with pytest.raises(ToolError, match="範囲の外"):
            await backend.call_tool(
                "demo_read_card", {"image": "evals/redteam/screenshots/echo-out-of-range.png"}
            )


def test_missing_tesseract_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLAB_TESSERACT", "echolab-no-such-ocr")
    assert not ocr.available()
    with pytest.raises(ocr.OcrError, match="tesseract-langpack-jpn"):
        ocr.read_lines(SHOTS / "echo-clean.png")
