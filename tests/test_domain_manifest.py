"""ドメインパックのマニフェスト（domains/*/domain.yaml）を検査する。

マニフェストの形式はコアとパックの契約（ADR-0003）なので、形式だけでなく
宣言した内容がパックの中身と食い違っていないことも確かめる。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_SCHEMA = json.loads((ROOT / "tests/schemas/domain.schema.json").read_text(encoding="utf-8"))
MANIFESTS = sorted(ROOT.glob("domains/*/domain.yaml"))


def _load(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _errors(schema: dict, doc: object) -> list[str]:
    validator = Draft202012Validator(schema)
    return [f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(doc)]


def _manifest_id(path: Path) -> str:
    return str(path.relative_to(ROOT))


def test_manifests_exist() -> None:
    assert MANIFESTS, "ドメインパックのマニフェストが 1 件も見つかりません"


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
def test_manifest_matches_schema(path: Path) -> None:
    assert _errors(DOMAIN_SCHEMA, _load(path)) == []


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
def test_manifest_name_matches_directory(path: Path) -> None:
    assert _load(path)["name"] == path.parent.name


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
@pytest.mark.parametrize("key", ["data_dir", "golden_dir", "prompts_dir"])
def test_manifest_dirs_exist(path: Path, key: str) -> None:
    target = path.parent / _load(path)[key]
    assert target.is_dir(), f"{key} が存在しません: {target.relative_to(ROOT)}"


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
def test_manifest_tool_names_are_unique(path: Path) -> None:
    names = [t["name"] for t in _load(path)["tools"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
def test_golden_tools_are_declared(path: Path) -> None:
    """ゴールデンケースで検査しているツールは、すべてマニフェストに宣言されていること。"""
    manifest = _load(path)
    declared = {t["name"] for t in manifest["tools"]}
    golden_files = sorted((path.parent / manifest["golden_dir"]).glob("*.yaml"))
    used = {_load(g)["tool"] for g in golden_files}
    assert used - declared == set(), f"マニフェストに無いツール: {sorted(used - declared)}"


@pytest.mark.parametrize("path", MANIFESTS, ids=_manifest_id)
def test_domain_prompt_mentions_every_tool(path: Path) -> None:
    """ドメインのプロンプト（system.md）が、宣言したツールの使い分けをすべて説明していること。"""
    manifest = _load(path)
    prompt = path.parent / manifest.get("prompts_dir", "prompts") / "system.md"
    if not prompt.is_file():
        pytest.skip("ドメインのプロンプトがありません")
    text = prompt.read_text(encoding="utf-8")
    wire_names = {t["name"].replace(".", "_") for t in manifest["tools"]}
    missing = sorted(n for n in wire_names if f"`{n}`" not in text)
    assert missing == [], f"プロンプトで説明していないツール: {missing}"
