"""ゴールデンケースとドメインデータの形式を JSON Schema で検査する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SCHEMA = json.loads((ROOT / "tests/schemas/golden.schema.json").read_text(encoding="utf-8"))
# ドメインのツールのケースと、コアの比較ツール（compare.*）のケース
GOLDEN_FILES = sorted([*ROOT.glob("domains/*/golden/*.yaml"), *ROOT.glob("core/golden/*.yaml")])
DATA_FILES = sorted(ROOT.glob("domains/*/data/*/*.yaml"))


def _load(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _errors(schema: dict, doc: object) -> list[str]:
    validator = Draft202012Validator(schema)
    return [f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(doc)]


def test_golden_files_exist() -> None:
    assert GOLDEN_FILES, "ゴールデンケースが 1 件も見つかりません"


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_golden_file_matches_schema(path: Path) -> None:
    assert _errors(GOLDEN_SCHEMA, _load(path)) == []


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_golden_case_ids_are_unique(path: Path) -> None:
    ids = [c["id"] for c in _load(path)["cases"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_data_file_has_schema_and_matches(path: Path) -> None:
    schema_path = path.parent / "schema" / f"{path.stem}.schema.json"
    assert schema_path.exists(), f"スキーマがありません: {schema_path.relative_to(ROOT)}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert _errors(schema, _load(path)) == []


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_unverified_data_has_todo_source(path: Path) -> None:
    """未確認（verified: false）の値には、出典が未記入であることを明示させる。"""

    def walk(node: object) -> list[dict]:
        if isinstance(node, dict):
            found = [node] if "verified" in node else []
            for v in node.values():
                found.extend(walk(v))
            return found
        if isinstance(node, list):
            return [x for v in node for x in walk(v)]
        return []

    for entry in walk(_load(path)):
        if not entry["verified"]:
            assert entry["source"].startswith("TODO"), entry


def test_every_tool_has_non_reference_case() -> None:
    """各ツールに、参照実装に依存しない根拠（手計算・閉形式）のケースを最低 1 件持たせる。

    YAML・Java・Python の 3 者一致は「一致」しか保証しない。期待値をすべて参照実装の
    出力から作ると、参照実装と Java が同じ誤りを共有していても検出できない。
    """
    derivations: dict[str, set[str]] = {}
    for path in GOLDEN_FILES:
        doc = _load(path)
        derivations.setdefault(doc["tool"], set()).update(c["derivation"] for c in doc["cases"])
    only_reference = sorted(t for t, d in derivations.items() if d <= {"reference"})
    assert only_reference == [], f"参照実装由来のケースしかないツール: {only_reference}"


GACHA_RULES_SCHEMA = json.loads(
    (ROOT / "domains/wuwa/data/v2.x/schema/gacha_rules.schema.json").read_text(encoding="utf-8")
)
_RULES = {
    "base_rate": 0.008,
    "soft_pity_start": 66,
    "soft_pity_increment": 0.04,
    "hard_pity": 80,
    "featured_rate": 0.5,
    "guarantee_after_loss": True,
}


def _banner(**fields: object) -> dict:
    banner = {"id": "test-banner", "display_name": "テスト", "rules": _RULES, **fields}
    return {"schema_version": 1, "banners": [banner]}


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"verified": True, "source": "TODO: 出典未記入"}, id="出典も確認日も無い"),
        pytest.param(
            {
                "verified": True,
                "source": "http://example.com/",
                "checked_at": "2026-10-01",
                "game_version": "2.3",
            },
            id="https でない出典",
        ),
        pytest.param(
            {"verified": True, "source": "https://example.com/", "game_version": "2.3"},
            id="確認日が無い",
        ),
        pytest.param(
            {"verified": True, "source": "https://example.com/", "checked_at": "2026-10-01"},
            id="ゲームの版が無い",
        ),
    ],
)
def test_verified_data_without_provenance_is_rejected(fields: dict) -> None:
    """verified: true なのに出典の URL・確認日・ゲームの版が揃わないものは弾く（ADR-0006）。"""
    assert _errors(GACHA_RULES_SCHEMA, _banner(**fields)) != []


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(
            {
                "verified": True,
                "source": "https://example.com/",
                "checked_at": "2026-10-01",
                "game_version": "2.3",
            },
            id="確認済みで出典が揃っている",
        ),
        pytest.param({"verified": False, "source": "TODO: 出典未記入"}, id="未確認"),
    ],
)
def test_data_with_valid_provenance_is_accepted(fields: dict) -> None:
    """出典が揃った確認済みの値と、未確認の値は通す（規則が厳しすぎないことの確認）。"""
    assert _errors(GACHA_RULES_SCHEMA, _banner(**fields)) == []
