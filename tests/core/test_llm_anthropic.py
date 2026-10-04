"""Claude（AnthropicLLM）の要求の組み立てと応答の正規化を、SDK のクライアントを偽物にして試す。

ネットワークにはつながない。実物の API での確認は手元で手動で行う（ADR-0008）。
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from core.agent import Agent, load_system_prompt
from core.agent.llm import AnthropicLLM, LLMError
from core.agent.llm.claude import FALLBACK_BETA
from core.contracts import ToolSpec
from core.gateway import Budget, Gateway
from core.trace import read_trace
from tests.core.fakes import FakeCalcBackend
from tests.core.test_agent import DMG_A, DMG_B

ROOT = Path(__file__).resolve().parents[2]


def message(
    content: list[dict[str, Any]],
    stop_reason: str,
    *,
    usage: dict[str, Any] | None = None,
    **extra: Any,
) -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": usage or {"input_tokens": 100, "output_tokens": 20},
            **extra,
        }
    )


class FakeClient:
    """``AsyncAnthropic`` の代わり。``beta.messages.create`` の引数を記録し、用意した応答を返す。"""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.beta = self
        self.messages = self

    async def create(self, **kwargs: Any) -> Any:
        # 履歴は後で追記されるので、呼ばれた時点の長さも残す
        self.requests.append({**kwargs, "_n_messages": len(kwargs["messages"])})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


TOOLS = [
    ToolSpec("echo_score", "声骸の採点", {"type": "object"}),
    ToolSpec("damage_expected", "期待ダメージ", {"type": "object", "required": ["atk"]}),
]


def test_request_construction() -> None:
    llm = AnthropicLLM(client=FakeClient([]))
    req = llm.build_request(
        system="規則", messages=[{"role": "user", "content": "質問"}], tools=TOOLS
    )
    assert req["model"] == "claude-opus-5-5"
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"] == {"effort": "medium"}
    assert req["max_tokens"] == 16000
    # 拒否されたときのサーバ側フォールバック（"default" 形式とそのベータ）
    assert req["fallbacks"] == "default"
    assert req["betas"] == [FALLBACK_BETA] == ["server-side-fallback-2026-07-01"]
    # 前置き（tools → system）の末尾に明示の区切り + 会話の末尾は自動キャッシュ
    assert req["system"] == [
        {"type": "text", "text": "規則", "cache_control": {"type": "ephemeral"}}
    ]
    assert req["cache_control"] == {"type": "ephemeral"}
    # ツールは名前順（前置きのバイト列を毎回同じにする）。強制のツール選択は使わない
    assert req["tools"] == [
        {
            "name": "damage_expected",
            "description": "期待ダメージ",
            "input_schema": {"type": "object", "required": ["atk"]},
        },
        {"name": "echo_score", "description": "声骸の採点", "input_schema": {"type": "object"}},
    ]
    assert "tool_choice" not in req
    assert "budget_tokens" not in json.dumps(req)
    assert req["messages"] == [{"role": "user", "content": "質問"}]


def test_effort_can_be_overridden() -> None:
    req = AnthropicLLM(client=FakeClient([]), effort="high").build_request(
        system="s", messages=[], tools=[]
    )
    assert req["output_config"] == {"effort": "high"}


async def test_response_is_normalized_and_content_kept_unchanged() -> None:
    resp = message(
        [
            {"type": "thinking", "thinking": "", "signature": "sig-1"},
            {"type": "text", "text": "計算します。"},
            {"type": "tool_use", "id": "toolu_1", "name": "damage_expected", "input": {"atk": 1}},
            {"type": "tool_use", "id": "toolu_2", "name": "echo_score", "input": {}},
        ],
        "tool_use",
        usage={
            "input_tokens": 50,
            "output_tokens": 30,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": None,
        },
    )
    llm = AnthropicLLM(client=FakeClient([resp]))
    turn = await llm.complete(system="s", messages=[{"role": "user", "content": "q"}], tools=TOOLS)
    assert turn.text == "計算します。"
    assert [(u.id, u.name, dict(u.input)) for u in turn.tool_uses] == [
        ("toolu_1", "damage_expected", {"atk": 1}),
        ("toolu_2", "echo_score", {}),
    ]
    assert turn.stop_reason == "tool_use"
    assert turn.usage == {
        "input_tokens": 50,
        "output_tokens": 30,
        "cache_creation_input_tokens": 2000,
        "cache_read_input_tokens": 0,
    }
    # 思考ブロック（署名付き）を含め、応答のブロックをそのまま履歴に戻す
    assert turn.raw_content == resp.content
    assert all(a is b for a, b in zip(turn.raw_content, resp.content, strict=True))
    assert [(c.model, c.usage["input_tokens"]) for c in turn.charges] == [("claude-opus-5-5", 50)]


async def test_fallback_iterations_are_charged_per_attempt() -> None:
    iteration = {"cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    resp = message(
        [{"type": "text", "text": "回答"}],
        "end_turn",
        usage={
            "input_tokens": 40,
            "output_tokens": 10,
            "iterations": [
                {"type": "message", "input_tokens": 40, "output_tokens": 0, **iteration},
                {
                    "type": "fallback_message",
                    "model": "claude-opus-4-8",
                    "input_tokens": 40,
                    "output_tokens": 10,
                    **iteration,
                },
            ],
        },
    )
    turn = await AnthropicLLM(client=FakeClient([resp])).complete(system="s", messages=[], tools=[])
    assert [(c.model, c.usage["output_tokens"]) for c in turn.charges] == [
        ("claude-opus-5-5", 0),
        ("claude-opus-4-8", 10),
    ]


async def test_refusal_is_reported_with_details() -> None:
    resp = message(
        [],
        "refusal",
        stop_details={"type": "refusal", "category": "cyber", "explanation": None},
    )
    turn = await AnthropicLLM(client=FakeClient([resp])).complete(system="s", messages=[], tools=[])
    assert turn.stop_reason == "refusal"
    assert turn.stop_details["category"] == "cyber"
    assert turn.tool_uses == ()


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    return cls(f"HTTP {status}", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (lambda: _status_error(anthropic.AuthenticationError, 401), "auth"),
        (lambda: _status_error(anthropic.PermissionDeniedError, 403), "auth"),
        (lambda: _status_error(anthropic.RateLimitError, 429), "transient"),
        (lambda: _status_error(anthropic.OverloadedError, 529), "transient"),
        (lambda: _status_error(anthropic.InternalServerError, 500), "transient"),
        (lambda: _status_error(anthropic.BadRequestError, 400), "other"),
        (lambda: _status_error(anthropic.NotFoundError, 404), "other"),
        (
            lambda: anthropic.APIConnectionError(
                request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            ),
            "transient",
        ),
        (
            lambda: anthropic.APITimeoutError(
                request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            ),
            "transient",
        ),
        (lambda: anthropic.CredentialsError("profile が読めません"), "credentials"),
    ],
)
async def test_api_errors_are_classified_by_type(error: Any, kind: str) -> None:
    client = FakeClient([error()])
    with pytest.raises(LLMError) as info:
        await AnthropicLLM(client=client).complete(system="s", messages=[], tools=[])
    assert info.value.kind == kind


async def test_unrelated_type_error_is_not_hidden() -> None:
    client = FakeClient([TypeError("プログラムの誤り")])
    with pytest.raises(TypeError, match="プログラムの誤り"):
        await AnthropicLLM(client=client).complete(system="s", messages=[], tools=[])


# ---------------------------------------------------------------------------
# Agent と組み合わせた往復（履歴の形・並列の結果のまとめ方・拒否）
# ---------------------------------------------------------------------------


async def _ask(tmp_path: Path, client: FakeClient, question: str = "比べて"):
    budget = Budget(tmp_path / "costs.jsonl", Decimal("1"), Decimal("10"))
    backend = FakeCalcBackend()
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": backend, "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        agent = Agent(
            gateway=gw,
            llm=AnthropicLLM(client=client),
            system_prompt=load_system_prompt(ROOT, "wuwa"),
            trace_dir=tmp_path / "traces",
        )
        return await agent.ask(question), backend, budget


async def test_agent_loop_over_mocked_sdk(tmp_path: Path) -> None:
    first = message(
        [
            {"type": "thinking", "thinking": "", "signature": "sig-1"},
            {"type": "tool_use", "id": "toolu_a", "name": "damage_expected", "input": DMG_A},
            {"type": "tool_use", "id": "toolu_b", "name": "damage_expected", "input": DMG_B},
        ],
        "tool_use",
        usage={"input_tokens": 3000, "output_tokens": 200, "cache_creation_input_tokens": 2500},
    )
    final = message(
        [{"type": "text", "text": "A は [[c1.total|0]]、B は [[c2.total|0]] です。"}],
        "end_turn",
        usage={"input_tokens": 400, "output_tokens": 50, "cache_read_input_tokens": 2500},
    )
    client = FakeClient([first, final])
    result, backend, budget = await _ask(tmp_path, client)

    assert result.status == "answered"
    assert result.answer == "A は 6,192、B は 7,128 です。"
    assert len(backend.calls) == 2

    # 2 回目の要求：質問 → 1 回目の応答（加工なし）→ 2 つの結果を 1 つの利用者メッセージで
    second = client.requests[1]
    msgs = second["messages"][: second["_n_messages"]]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == first.content
    assert msgs[1]["content"][0].signature == "sig-1"
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_a", "toolu_b"]
    assert all(r["type"] == "tool_result" and "is_error" not in r for r in results)
    # 前置きは毎回同じ（キャッシュが効く）
    assert client.requests[0]["system"] == second["system"]
    assert client.requests[0]["tools"] == second["tools"]

    # 費用（100 万トークンあたりの単価）：3000×4 + 200×20 + 2500×5 = 28500、
    # 400×4 + 50×20 + 2500×0.2 = 3100
    assert result.cost_usd == Decimal("0.0316")
    assert budget.spent_today() == Decimal("0.0316")
    calls = read_trace(result.trace_path, "llm_call")
    assert [c["usd"] for c in calls] == ["0.0285", "0.0031"]


async def test_agent_refusal_does_not_run_partial_tool_use(tmp_path: Path) -> None:
    refused = message(
        [{"type": "tool_use", "id": "toolu_x", "name": "damage_expected", "input": DMG_A}],
        "refusal",
        stop_details={"type": "refusal", "category": None, "explanation": None},
    )
    client = FakeClient([refused])
    result, backend, _ = await _ask(tmp_path, client)
    assert result.status == "refusal"
    assert backend.calls == []
    assert len(client.requests) == 1
    [call] = read_trace(result.trace_path, "llm_call")
    assert call["stop_reason"] == "refusal"


async def test_missing_credentials_become_llm_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """実物の SDK のクライアントで、認証情報が無いときの例外を確かめる（通信はしない）。"""
    import os

    for name in list(os.environ):
        if name.startswith("ANTHROPIC_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path))  # ant auth login の設定も見つからないようにする
    client = anthropic.AsyncAnthropic(base_url="http://127.0.0.1:9", max_retries=0)
    with pytest.raises(LLMError, match="認証情報") as info:
        await AnthropicLLM(client=client).complete(system="s", messages=[], tools=[])
    assert info.value.kind == "credentials"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("credentials", "ANTHROPIC_API_KEY"),
        ("auth", "ANTHROPIC_API_KEY"),
        ("transient", "時間をおいて"),
        ("other", "トレース"),
    ],
)
async def test_llm_error_answer_names_the_cause(tmp_path: Path, kind: str, expected: str) -> None:
    import re

    class Broken:
        model = "claude-opus-5-5"

        async def complete(self, **_: Any):
            raise LLMError("失敗", kind=kind)

    budget = Budget(tmp_path / "costs.jsonl", Decimal("1"), Decimal("10"))
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": FakeCalcBackend(), "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        agent = Agent(
            gateway=gw,
            llm=Broken(),
            system_prompt=load_system_prompt(ROOT, "wuwa"),
            trace_dir=tmp_path / "traces",
        )
        result = await agent.ask("期待ダメージは？")
    assert result.status == "llm_error"
    assert expected in result.answer
    assert not re.search(r"\d", result.answer)  # 定型の回答は数字を含まない
    if kind != "transient":
        assert "時間をおいて" not in result.answer
    [event] = read_trace(result.trace_path, "llm_error")
    assert event["kind"] == kind
