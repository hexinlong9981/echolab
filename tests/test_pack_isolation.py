"""CI の「パックの変更でコアを変えない」検査（.github/scripts/check_pack_isolation.py）の試験。

一時的な git リポジトリでコミットを作り、規則どおりに合否が出ることを確かめる。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_pack_isolation", ROOT / ".github/scripts/check_pack_isolation.py"
)
assert _spec is not None and _spec.loader is not None
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    # 最初のパック（wuwa）はコアと一緒に作ってよい
    _commit(tmp_path, {"core/a.py": "1", "domains/wuwa/domain.yaml": "name: wuwa"}, "M1")
    return tmp_path


def test_pack_added_without_core_changes_passes(repo: Path, capsys: pytest.CaptureFixture) -> None:
    base = _commit(repo, {"core/a.py": "2"}, "core の汎用化")
    _commit(repo, {"domains/loan/domain.yaml": "name: loan", "tests/t.py": "x"}, "パック")
    assert check.main(["--base", base, "--repo", str(repo)]) == 0
    assert "OK: 1 件" in capsys.readouterr().out


def test_commit_touching_core_and_domains_fails(repo: Path, capsys: pytest.CaptureFixture) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, {"core/a.py": "2", "domains/wuwa/x.yaml": "y"}, "混ぜた")
    assert check.main(["--base", base, "--repo", str(repo)]) == 1
    assert "domains/ と core/ の両方" in capsys.readouterr().err


def test_pack_added_with_core_changes_fails_even_outside_the_range(
    repo: Path, capsys: pytest.CaptureFixture
) -> None:
    _commit(repo, {"core/a.py": "2", "domains/loan/domain.yaml": "name: loan"}, "混ぜた")
    base = _commit(repo, {"README.md": "x"}, "あと")
    assert check.main(["--base", base, "--repo", str(repo)]) == 1
    err = capsys.readouterr().err
    assert "パック loan を追加したコミットが core/ を変えています" in err


@pytest.mark.parametrize("base", ["", "0" * 40, "f" * 40])
def test_unknown_base_checks_only_head(repo: Path, base: str) -> None:
    _commit(repo, {"core/a.py": "2", "domains/wuwa/x.yaml": "y"}, "混ぜた")
    _commit(repo, {"README.md": "x"}, "あと")  # head だけなら違反は無い
    assert check.main(["--base", base, "--repo", str(repo)]) == 0


def test_this_repository_follows_the_rules() -> None:
    """このリポジトリの全パックの追加について規則 2 を確かめる（浅いクローンでは省く）。"""
    if _git(ROOT, "rev-parse", "--is-shallow-repository") == "true":
        pytest.skip("浅いクローンでは履歴を確かめられない")
    assert check.packs_added_with_core_changes("HEAD", cwd=ROOT) == []
