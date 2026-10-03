"""CLI（``python -m core.agent``）の終了コードと、設定・起動の誤りの表示。

API キー・Java は使わない（台本と偽の計算サービス、または起動前の検査で止まる場合だけ）。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

from core.agent.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "core/agent/examples/compare_builds.yaml"
QUESTION = "ビルド A と B ではどちらが強い？"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """本物の台帳を汚さないよう、台帳の既定の場所を一時ディレクトリにする。"""
    ledger = tmp_path / "real-ledger.jsonl"
    monkeypatch.setenv("ECHOLAB_LEDGER", str(ledger))
    for name in ("ECHOLAB_DAILY_USD", "ECHOLAB_MONTHLY_USD"):
        monkeypatch.delenv(name, raising=False)
    return ledger


def run_cli(tmp_path: Path, *args: str) -> int:
    return main([QUESTION, "--trace-dir", str(tmp_path / "traces"), *args])


def test_scripted_run_does_not_write_the_real_ledger(
    tmp_path: Path, _isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(tmp_path, "--llm", "scripted", "--script", str(SCRIPT), "--fake-backend")
    out = capsys.readouterr().out
    assert code == 0
    assert "状態: answered" in out
    # 偽の計算サービスも calc-engine と同じく小数点以下 6 桁で返す
    assert "6192.000000 " in out and "6192.000000000000" not in out
    assert not _isolated.exists()


@pytest.mark.parametrize("fake", [False, True])
def test_unknown_domain_is_the_same_error_with_or_without_fake_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake: bool
) -> None:
    args = ["--llm", "scripted", "--script", str(SCRIPT), "--domain", "nope"]
    code = run_cli(tmp_path, *args, *(["--fake-backend"] if fake else []))
    err = capsys.readouterr().err
    assert code == 2
    assert "エラー: ドメインが見つかりません: nope（使えるドメイン: mortgage、wuwa）" in err
    assert "Traceback" not in err


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--llm", "scripted", "--fake-backend"], "--script（台本の YAML）が必要です"),
        (
            ["--llm", "scripted", "--script", "no-such.yaml", "--fake-backend"],
            "台本が見つかりません",
        ),
    ],
)
def test_usage_errors_exit_with_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    assert run_cli(tmp_path, *args) == 2
    err = capsys.readouterr().err
    assert message in err and "Traceback" not in err


def test_debug_flag_shows_the_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--llm", "scripted", "--script", str(SCRIPT), "--domain", "nope", "--debug"]
    assert run_cli(tmp_path, *args) == 2
    err = capsys.readouterr().err
    assert "Traceback" in err and "UnknownDomainError" in err


def test_missing_java_is_reported_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("JAVA_HOME", raising=False)
    assert run_cli(tmp_path, "--llm", "scripted", "--script", str(SCRIPT)) == 2
    err = capsys.readouterr().err
    assert "実行ファイル java が見つかりません" in err and "JAVA_HOME" in err
    assert "Traceback" not in err


def test_missing_jar_is_reported_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "config", repo / "config")
    (repo / "domains").symlink_to(ROOT / "domains")
    services = yaml.safe_load((repo / "config/services.yaml").read_text(encoding="utf-8"))
    # java の有無に左右されないよう、実行ファイルは Python にする（-jar の検査だけを試す）
    services["services"]["calc-engine"]["command"] = [
        sys.executable,
        "-jar",
        "svc/build/libs/missing.jar",
    ]
    (repo / "config/services.yaml").write_text(yaml.safe_dump(services), encoding="utf-8")
    code = run_cli(tmp_path, "--llm", "scripted", "--script", str(SCRIPT), "--repo-root", str(repo))
    err = capsys.readouterr().err
    assert code == 2
    assert f"jar がありません: {repo / 'svc/build/libs/missing.jar'}" in err
    assert "./gradlew bootJar" in err and "Traceback" not in err


def test_invalid_cap_setting_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ECHOLAB_DAILY_USD", "one")
    code = run_cli(tmp_path, "--llm", "scripted", "--script", str(SCRIPT), "--fake-backend")
    err = capsys.readouterr().err
    assert code == 2
    assert "環境変数 ECHOLAB_DAILY_USD の値「one」" in err and "Traceback" not in err


def test_corrupt_ledger_is_reported_before_calling_the_llm(
    tmp_path: Path, _isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _isolated.write_text("{壊れた行\n", encoding="utf-8")
    code = run_cli(tmp_path, "--llm", "anthropic", "--fake-backend")
    err = capsys.readouterr().err
    assert code == 2
    assert f"コストの台帳 {_isolated} の 1 行目が読めない" in err and "Traceback" not in err
