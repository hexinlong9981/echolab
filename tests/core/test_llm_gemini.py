"""GeminiLLM の要求の組み立てと応答の正規化を、SDK クライアントを偽物にしてテストする。

ネットワークにはつながない。実物の API での確認は手元で手動で行う（ADR-0008）。
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors, types

from core.agent import Agent, load_system_prompt
from core.agent.llm import GeminiLLM, LLMError
from core.contracts import ToolSpec
from core.gateway import Budget, Gateway
from core.trace import read_trace
from tests.core.fakes import FakeCalcBackend
from tests.core.test_agent import DMG_A

ROOT = Path(__file__).resolve().parents[2]


def make_response(
    parts: list[types.Part],
    *,
    finish_reason: types.FinishReason | str = types.FinishReason.STOP,
    prompt_tokens: int = 100,
    candidates_tokens: int = 20,
    cached_tokens: int = 0,
    model_version: str = "gemini-2.5-flash",
) -> Any:
    content = types.Content(role="model", parts=parts)
    candidate = types.Candidate(
        content=content,
        finish_reason=finish_reason if isinstance(finish_reason, types.FinishReason) else None,
    )
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt_tokens,
        candidates_token_count=candidates_tokens,
        cached_content_token_count=cached_tokens,
    )
    resp = types.GenerateContentResponse(
        candidates=[candidate],
        usage_metadata=usage,
        model_version=model_version,
    )
    return resp


class FakeGeminiClient:
    """genai.Client の代わり。aio.models.generate_content の引数を記録し、用意した応答を返す。"""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

        class _Aio:
            class _Models:
                def __init__(self, outer: FakeGeminiClient) -> None:
                    self._outer = outer

                async def generate_content(self, **kwargs: Any) -> Any:
                    self._outer.requests.append(dict(kwargs))
                    item = self._outer.responses.pop(0)
                    if isinstance(item, Exception):
                        raise item
                    return item

            def __init__(self, outer: FakeGeminiClient) -> None:
                self.models = self._Models(outer)

        self.aio = _Aio(self)


TOOLS = [
    ToolSpec("echo_score", "声骸の採点", {"type": "object"}),
    ToolSpec("damage_expected", "期待ダメージ", {"type": "object", "required": ["atk"]}),
]


def test_request_construction() -> None:
    client = FakeGeminiClient([])
    llm = GeminiLLM(client=client, model="gemini-2.5-flash", max_tokens=4096)
    req = llm.build_request(
        system="システム指示",
        messages=[{"role": "user", "content": "質問文"}],
        tools=TOOLS,
    )

    assert req["model"] == "gemini-2.5-flash"
    cfg: types.GenerateContentConfig = req["config"]
    assert cfg.system_instruction == "システム指示"
    assert cfg.temperature == 0.0
    assert cfg.max_output_tokens == 4096
    assert cfg.automatic_function_calling.disable is True

    # ツールは名前順で整列される
    tool_decls = cfg.tools[0].function_declarations
    assert len(tool_decls) == 2
    assert tool_decls[0].name == "damage_expected"
    assert tool_decls[0].description == "期待ダメージ"
    assert tool_decls[0].parameters_json_schema == {"type": "object", "required": ["atk"]}
    assert tool_decls[1].name == "echo_score"

    contents = req["contents"]
    assert len(contents) == 1
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "質問文"


def test_build_contents_multiturn_and_tool_results() -> None:
    llm = GeminiLLM(client=FakeGeminiClient([]))
    llm._tool_call_names["call_damage_expected_01"] = "damage_expected"

    messages = [
        {"role": "user", "content": "質問"},
        {
            "role": "assistant",
            "content": types.Content(
                role="model",
                parts=[types.Part.from_function_call(name="damage_expected", args={"atk": 2000})],
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_damage_expected_01",
                    "content": json.dumps({"values": {"c1.total": "4500"}}),
                }
            ],
        },
        {"role": "user", "content": "修正してください"},
    ]

    contents = llm.build_contents(messages)
    assert len(contents) == 4
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "質問"

    assert contents[1].role == "model"
    assert contents[1].parts[0].function_call.name == "damage_expected"
    assert contents[1].parts[0].function_call.args == {"atk": 2000}

    assert contents[2].role == "user"
    fr = contents[2].parts[0].function_response
    assert fr.name == "damage_expected"
    assert fr.response == {"values": {"c1.total": "4500"}}

    assert contents[3].role == "user"
    assert contents[3].parts[0].text == "修正してください"


def test_response_normalization_and_thought_filtering() -> None:
    llm = GeminiLLM(client=FakeGeminiClient([]))
    resp = make_response(
        parts=[
            types.Part(text="推論中: 2000 * 1.5 ...", thought=True),
            types.Part(text="計算します。"),
            types.Part.from_function_call(name="damage_expected", args={"atk": 2000}),
        ],
        prompt_tokens=150,
        candidates_tokens=30,
        cached_tokens=50,
    )

    turn = llm.to_turn(resp, requested_model="gemini-2.5-flash")
    # 思考ブロック（thought=True）はテキストから除外される
    assert turn.text == "計算します。"
    assert turn.texts == ("計算します。",)

    # ツール呼び出しが抽出される
    assert len(turn.tool_uses) == 1
    tu = turn.tool_uses[0]
    assert tu.name == "damage_expected"
    assert tu.input == {"atk": 2000}
    assert tu.id.startswith("call_damage_expected_")
    assert turn.stop_reason == "tool_use"

    # 使用量と課金情報
    assert turn.usage["input_tokens"] == 150
    assert turn.usage["output_tokens"] == 30
    assert turn.usage["cache_read_input_tokens"] == 50
    assert turn.usage["cache_creation_input_tokens"] == 0
    assert len(turn.charges) == 1
    assert turn.charges[0].model == "gemini-2.5-flash"


def test_finish_reason_stop_and_refusal() -> None:
    llm = GeminiLLM(client=FakeGeminiClient([]))

    # 通常終了
    turn_ok = llm.to_turn(
        make_response(
            [types.Part(text="回答")],
            finish_reason=types.FinishReason.STOP,
        ),
        requested_model="gemini-2.5-flash",
    )
    assert turn_ok.stop_reason == "end_turn"

    # 安全による拒否
    turn_refusal = llm.to_turn(
        make_response(
            [],
            finish_reason=types.FinishReason.SAFETY,
        ),
        requested_model="gemini-2.5-flash",
    )
    assert turn_refusal.stop_reason == "refusal"

    # トークン超過
    turn_max = llm.to_turn(
        make_response(
            [types.Part(text="途中で切")],
            finish_reason=types.FinishReason.MAX_TOKENS,
        ),
        requested_model="gemini-2.5-flash",
    )
    assert turn_max.stop_reason == "max_tokens"


def test_error_mapping() -> None:
    from core.agent.llm.gemini import to_llm_error

    err_cred = to_llm_error(DefaultCredentialsError("認証なし"))
    assert isinstance(err_cred, LLMError)
    assert err_cred.kind == "credentials"

    err_auth = to_llm_error(errors.APIError(403, {"error": {"message": "権限なし"}}))
    assert err_auth.kind == "auth"

    err_transient_429 = to_llm_error(errors.APIError(429, {"error": {"message": "混雑"}}))
    assert err_transient_429.kind == "transient"

    err_transient_503 = to_llm_error(errors.APIError(503, {"error": {"message": "停止中"}}))
    assert err_transient_503.kind == "transient"

    err_other = to_llm_error(errors.APIError(400, {"error": {"message": "引数誤り"}}))
    assert err_other.kind == "other"


@pytest.mark.asyncio
async def test_agent_with_gemini_llm_flow(tmp_path: Path) -> None:
    """GeminiLLM を介した Agent の質問 → ツール呼出 → 結果解釈 → 回答の閉環テスト。"""
    # 1 往復目: ツール呼び出し
    resp1 = make_response(
        parts=[
            types.Part.from_function_call(name="damage_expected", args=DMG_A),
        ],
        prompt_tokens=100,
        candidates_tokens=20,
    )
    # 2 往復目: プレースホルダによる最終回答
    resp2 = make_response(
        parts=[
            types.Part(text="期待ダメージは [[c1.total|0]] です。"),
        ],
        prompt_tokens=150,
        candidates_tokens=15,
    )

    client = FakeGeminiClient([resp1, resp2])
    llm = GeminiLLM(client=client, model="gemini-2.5-flash")

    budget = Budget(
        tmp_path / "costs.jsonl",
        Decimal("1.00"),
        Decimal("10.00"),
    )
    backend = FakeCalcBackend()
    async with await Gateway.open(
        ROOT,
        "wuwa",
        backends={"calc-engine": backend, "vision-mcp": FakeCalcBackend()},
        budget=budget,
    ) as gw:
        agent = Agent(
            gateway=gw,
            llm=llm,
            system_prompt=load_system_prompt(ROOT, "wuwa"),
            trace_dir=tmp_path / "traces",
            domain="wuwa",
        )

        result = await agent.ask("期待ダメージは？")
        assert result.status == "answered"
        assert len(result.cited) == 1
        assert result.cited[0].source_id == "c1.total"
        assert result.cost_usd > Decimal(0)

        # トレースの検証
        events = read_trace(result.trace_path)
        types_seq = [e["event"] for e in events]
        assert types_seq == [
            "question",
            "llm_call",
            "tool_call",
            "tool_result",
            "llm_call",
            "verdict",
            "answer",
        ]
