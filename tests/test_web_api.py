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
    assert {s["id"] for s in index["suites"]} == {
        "faithfulness",
        "mortgage",
        "redteam",
        "mushoku",
        "spoilers",
    }
    assert all(s["ok"] and s["faithfulness"] == 1.0 for s in index["suites"])
    assert index["services"]["echo.read_screenshot"] == "vision-mcp"
    assert index["services"]["compare.diff"] == "core"

    # 実行のファイル名は公開のたびに変わらないキー（デモの ID か <評価>-<ケース>）
    keys = {d["key"] for d in index["demos"]} | {
        c["key"] for s in index["suites"] for c in s["cases"] if c["key"]
    }
    assert keys == {p.stem for p in (out / "runs").glob("*.json")}
    assert {d["key"] for d in index["demos"]} == {d["id"] for d in DEMOS}
    assert all(
        c["key"] == f"{s['id']}-{c['id']}" for s in index["suites"] for c in s["cases"] if c["key"]
    )
    for path in [out / "index.json", *(out / "runs").glob("*.json")]:
        text = path.read_text(encoding="utf-8")
        # 手元のパスを公開しない
        assert str(REPO_ROOT) not in text and "/tmp/" not in text, path.name
    first = json.loads((out / "runs" / f"{index['demos'][0]['key']}.json").read_text("utf-8"))
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


def test_question_list_for_translations_is_up_to_date() -> None:
    """web/src/locales/questions.ja.json（英中の訳のキー）が、デモと評価ケースの質問と一致すること。"""
    import yaml

    questions = [d["question"] for d in DEMOS]
    for cases in (
        "faithfulness/cases.yaml",
        "faithfulness/mortgage.yaml",
        "redteam/cases.yaml",
        "faithfulness/mushoku.yaml",
        "redteam/spoilers.yaml",
    ):
        doc = yaml.safe_load((REPO_ROOT / "evals" / cases).read_text(encoding="utf-8"))
        questions += [c["question"] for c in doc["cases"]]
    listed = json.loads(
        (REPO_ROOT / "web/src/locales/questions.ja.json").read_text(encoding="utf-8")
    )
    assert sorted(set(questions)) == sorted(listed), (
        "質問を変えたら、訳（web/src/locales/questions.*.json）も直す"
    )


def test_progress_is_passed_as_user_context() -> None:
    params = server.parse_ask(
        {"llm": "anthropic", "question": "q", "domain": "mushoku", "progress": "novel:5"}
    )
    assert params["context"] == {"progress": "novel:5"}
    demo = server.parse_ask({"llm": "scripted", "demo": "demo-mushoku"})
    assert demo["context"] == {"progress": "novel:3"} and demo["domain"] == "mushoku"
    with pytest.raises(server.ApiError, match="progress は"):
        server.parse_ask({"llm": "anthropic", "question": "q", "domain": "mushoku", "progress": 5})


def test_domains_are_shown_in_the_preferred_order() -> None:
    assert server.ordered_domains(["mortgage", "mushoku", "wuwa", "zzz", "abc"]) == [
        "wuwa",
        "mushoku",
        "mortgage",
        "abc",
        "zzz",
    ]
    assert server.info()["domains"][:3] == ["wuwa", "mushoku", "mortgage"]


# ---------------------------------------------------------------------------
# 公開のデモサーバ（servers/web_api/public.py、ADR-0013）
# ---------------------------------------------------------------------------

from servers.web_api import public  # noqa: E402

SITE = "https://echolab-web.echolab-web.workers.dev"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"llm": "anthropic", "question": "q", "domain": "wuwa"}, "llm_not_allowed"),
        ({"demo": "demo-mortgage", "fake_backend": True}, "fake_not_allowed"),
        ({"demo": "../../etc/passwd"}, "unknown_demo"),
        ({}, "unknown_demo"),
    ],
)
def test_public_mode_only_runs_known_demos_with_scripted_llm(body: dict, code: str) -> None:
    with pytest.raises(public.PublicError) as e:
        public.parse_public_ask(body)
    assert e.value.code == code


def test_public_mode_uses_real_services() -> None:
    params = public.parse_public_ask({"demo": "demo-mortgage"})
    assert params["llm_kind"] == "scripted" and params["fake_backend"] is False


def test_rate_limiter_per_minute_and_per_day() -> None:
    now = [0.0]
    limiter = public.RateLimiter(per_minute=2, per_day=3, clock=lambda: now[0])
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(public.PublicError) as e:
        limiter.check("a")
    assert e.value.status == 429 and e.value.retry_after == 60
    limiter.check("b")  # 接続元ごとに数える
    now[0] = 61.0
    limiter.check("a")
    now[0] = 130.0
    with pytest.raises(public.PublicError, match="1 日"):
        limiter.check("a")
    now[0] = 86400 + 10.0
    limiter.check("a")  # 1 日たてば戻る


def test_runner_rejects_when_the_queue_is_full() -> None:
    gate = threading.Event()
    started = threading.Event()

    def slow(_: dict) -> dict:
        started.set()
        gate.wait(5)
        return {"ok": True}

    runner = public.Runner(slow, queue_max=0)
    t = threading.Thread(target=runner, args=({},))
    t.start()
    started.wait(5)
    with pytest.raises(public.PublicError) as e:
        runner({})
    assert e.value.code == "busy"
    gate.set()
    t.join(5)


@pytest.fixture
def public_url() -> Iterator[str]:
    calls: list[dict] = []

    def fake_run(params: dict) -> dict:
        calls.append(params)
        return {"run_id": "r", "status": "answered", "events": [], "live": {"elapsed_ms": 1}}

    httpd = public.make_public_server(
        "127.0.0.1",
        0,
        limiter=public.RateLimiter(per_minute=2, per_day=10),
        runner=public.Runner(fake_run),
        origins=frozenset({SITE}),
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _request(url: str, method: str, headers: dict[str, str], body: object = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_public_health_and_cors(public_url: str) -> None:
    status, headers, body = _request(f"{public_url}/api/health", "GET", {"Origin": SITE})
    doc = json.loads(body)
    assert status == 200 and doc["mode"] == "public" and doc["llm"] == "scripted"
    assert headers["Access-Control-Allow-Origin"] == SITE

    # CORS の事前確認（application/json の POST の前にブラウザが送る）
    status, headers, _ = _request(
        f"{public_url}/api/ask",
        "OPTIONS",
        {
            "Origin": SITE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == SITE
    assert "POST" in headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in headers["Access-Control-Allow-Headers"]

    status, headers, _ = _request(
        f"{public_url}/api/ask", "OPTIONS", {"Origin": "https://evil.example"}
    )
    assert status == 403 and "Access-Control-Allow-Origin" not in headers


def test_public_ask_origin_llm_and_rate_limit(public_url: str) -> None:
    json_headers = {"Content-Type": "application/json", "Origin": SITE}
    status, headers, body = _request(
        f"{public_url}/api/ask", "POST", json_headers, {"demo": "demo-mortgage"}
    )
    assert status == 200 and json.loads(body)["status"] == "answered"
    assert headers["Access-Control-Allow-Origin"] == SITE

    status, _, body = _request(
        f"{public_url}/api/ask",
        "POST",
        json_headers,
        {"llm": "anthropic", "question": "q", "domain": "wuwa"},
    )
    assert status == 403 and json.loads(body)["code"] == "llm_not_allowed"

    evil = {"Content-Type": "application/json", "Origin": "https://evil.example"}
    status, _, body = _request(f"{public_url}/api/ask", "POST", evil, {"demo": "demo-mortgage"})
    assert status == 403 and json.loads(body)["code"] == "forbidden_origin"

    _request(f"{public_url}/api/ask", "POST", json_headers, {"demo": "demo-mortgage"})
    status, headers, body = _request(
        f"{public_url}/api/ask", "POST", json_headers, {"demo": "demo-mortgage"}
    )
    assert status == 429 and json.loads(body)["code"] == "rate_limited"
    assert headers["Retry-After"] == "60"


def test_public_run_hides_local_paths() -> None:
    record = public.run_demo(public.parse_public_ask({"demo": "demo-mortgage"}))
    text = json.dumps(record, ensure_ascii=False)
    assert record["status"] == "answered" and record["fake_backend"] is False
    assert str(REPO_ROOT) not in text and "/tmp/" not in text
    assert record["live"]["elapsed_ms"] >= 0


def test_local_server_refuses_host_without_public() -> None:
    with pytest.raises(SystemExit):
        server.main(["--host", "0.0.0.0"])


def test_public_client_ip_uses_the_last_forwarded_hop() -> None:
    """Cloud Run の前段は X-Forwarded-For の末尾に本当の接続元を付ける。先頭は偽装できる。"""
    from servers.web_api.public import client_ip

    assert client_ip("1.2.3.4, 203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert client_ip("203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert client_ip("", "10.0.0.1") == "10.0.0.1"  # 前段が無い（手元の試験）


def test_public_port_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """--public で --port を省くと、Cloud Run が渡す PORT で待ち受ける。"""
    from servers.web_api import server as server_mod

    seen: dict[str, object] = {}

    class Dummy:
        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    def fake_make_public_server(host: str, port: int) -> Dummy:
        seen.update(host=host, port=port)
        return Dummy()

    import servers.web_api.public as public_mod

    monkeypatch.setattr(public_mod, "make_public_server", fake_make_public_server)
    monkeypatch.setenv("PORT", "9123")
    assert server_mod.main(["--public"]) == 0
    assert seen == {"host": "0.0.0.0", "port": 9123}
