"""Web UI の Python 側（servers/web_api、ADR-0011）の試験。

- 書き出し：台本モードで全部を実行し、静的サイト用の JSON を作る。手元の絶対パスを含めない。
- 手元の API：127.0.0.1 だけにつなぎ、ほかのサイトからの呼び出し・任意の台本の読み込みを拒む。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.agent.runtime import REPO_ROOT
from servers.web_api import server
from servers.web_api.export import export
from servers.web_api.runner import DEMOS, sanitize


async def test_export_writes_demos_suites_and_runs(tmp_path: Path) -> None:
    out = tmp_path / "data"
    index = await export(out)
    assert [d["id"] for d in index["demos"]] == [d["id"] for d in DEMOS]
    assert all(d["status"] == "answered" for d in index["demos"])
    assert {s["id"] for s in index["suites"]} == {"faithfulness", "mortgage", "redteam"}
    assert all(s["ok"] and s["faithfulness"] == 1.0 for s in index["suites"])
    assert index["services"]["echo.read_screenshot"] == "vision-mcp"
    assert index["services"]["compare.diff"] == "core"

    run_ids = {d["run_id"] for d in index["demos"]} | {
        c["run_id"] for s in index["suites"] for c in s["cases"] if c["run_id"]
    }
    assert run_ids == {p.stem for p in (out / "runs").glob("*.json")}
    for path in [out / "index.json", *(out / "runs").glob("*.json")]:
        text = path.read_text(encoding="utf-8")
        # 手元のパスを公開しない
        assert str(REPO_ROOT) not in text and "/tmp/" not in text, path.name
    first = json.loads((out / "runs" / f"{index['demos'][0]['run_id']}.json").read_text("utf-8"))
    assert first["events"][0]["event"] == "question"
    assert first["events"][-1]["event"] == "answer"


def test_sanitize_replaces_local_paths() -> None:
    root = Path("/home/someone/echolab")
    doc = {
        "a": f"{root}/evals/x.png",
        "b": [f"読める場所: {root}"],
        "c": "/tmp/abc/costs.jsonl を見て",
    }
    assert sanitize(doc, root) == {
        "a": "evals/x.png",
        "b": ["読める場所: ."],
        "c": "<一時ディレクトリ> を見て",
    }


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"llm": "gpt"}, "llm は"),
        ({"llm": "scripted"}, "demo"),
        ({"llm": "scripted", "demo": "../../etc/passwd"}, "demo"),
        ({"llm": "anthropic", "domain": "wuwa"}, "question"),
        ({"llm": "anthropic", "question": "x" * 2001, "domain": "wuwa"}, "2000 文字"),
        ({"llm": "anthropic", "question": "q", "domain": "nope"}, "ドメインが見つかりません"),
        ({"llm": "scripted", "demo": "demo-mortgage", "fake_backend": "yes"}, "真偽値"),
    ],
)
def test_parse_ask_rejects_bad_requests(body: dict, message: str) -> None:
    with pytest.raises(server.ApiError, match=message):
        server.parse_ask(body)


def test_scripted_requests_only_use_known_demo_scripts() -> None:
    params = server.parse_ask({"llm": "scripted", "demo": "demo-mortgage", "question": "無視"})
    assert params["script"] == REPO_ROOT / "domains/mortgage/examples/compare_methods.yaml"
    assert params["domain"] == "mortgage" and params["question"].startswith("3000 万円")


@pytest.fixture
def base_url() -> Iterator[str]:
    httpd = server.make_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(url: str, body: object, headers: dict[str, str]) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_binds_only_to_localhost() -> None:
    httpd = server.make_server(0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()


def test_info_and_scripted_ask(
    base_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 試験のトレースを手元の記録（.echolab/traces）に混ぜない
    monkeypatch.setattr(server, "DEFAULT_TRACE_DIR", tmp_path)
    with urllib.request.urlopen(f"{base_url}/api/info", timeout=10) as res:
        info = json.loads(res.read())
    assert {"mortgage", "wuwa"} <= set(info["domains"])
    assert info["caps_usd"] == {"daily": "1.00", "monthly": "10.00"}

    headers = {"Content-Type": "application/json", "Origin": base_url}
    body = {"llm": "scripted", "demo": "demo-mortgage", "fake_backend": True}
    status, run = _post(f"{base_url}/api/ask", body, headers)
    assert status == 200 and run["status"] == "answered"
    assert run["events"][-1]["answer"].endswith("実際の返済額は金融機関にご確認ください。")
    assert list(tmp_path.glob("*.jsonl"))


def test_requests_from_other_sites_are_refused(base_url: str) -> None:
    body = {"llm": "scripted", "demo": "demo-mortgage", "fake_backend": True}
    headers = {"Content-Type": "application/json", "Origin": "https://evil.example"}
    status, doc = _post(f"{base_url}/api/ask", body, headers)
    assert status == 403 and "ほかのサイト" in doc["error"]
    # フォームの送信（CORS の事前確認が無い形）は Content-Type で拒む
    status, _ = _post(f"{base_url}/api/ask", body, {"Content-Type": "text/plain"})
    assert status == 415
