"""Claude（公式 SDK の AsyncAnthropic）による LLM の実装。

要求の組み立て（ADR-0008 と、利用者の決定に従う）:

- モデルは ``claude-opus-5-5``。思考は適応型（このモデルでは無効にできない）で、深さは
  ``output_config.effort`` で明示する。既定は ``medium``：ツールを選び、出典 ID を引用して
  短い文を組み立てるだけの作業で、難しい推論は計算サービスが受け持つため。
  コストの上限（日次 1 USD）の中で回数を確保する意味もある。評価で品質が足りなければ上げる。
- 安全分類器による拒否に備えて、サーバ側のフォールバック（``fallbacks: "default"``、
  ベータ ``server-side-fallback-2026-07-01``）を付ける。それでも ``stop_reason`` が
  ``refusal`` なら、Agent が数値を含まない回答で終える。
- プロンプトキャッシュ：変わらない前置き（ツール定義 → システムプロンプト）の末尾に明示の
  区切りを置き、伸びていく会話の末尾は自動キャッシュ（最上位の ``cache_control``）に任せる。
  ツールは名前順に並べ、前置きのバイト列を毎回同じにする。
- 応答の内容は加工せずに履歴へ戻す（思考ブロックの署名を保つため。履歴は追記のみ）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import anthropic

from core.agent.llm.base import Charge, LLMError, LLMTurn, ToolUse, normalize_usage
from core.contracts import ToolSpec

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
#: 非ストリーミングの要求で HTTP のタイムアウトにかからない上限（思考の分も含む）。
DEFAULT_MAX_TOKENS = 16000
#: サーバ側フォールバックの "default" 形式に必要なベータ（配列形式の -06-01 とは別）。
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicLLM:
    """Claude API を呼ぶ LLM。API キーなどの認証情報は SDK の既定の解決順に従う。"""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client if client is not None else anthropic.AsyncAnthropic()

    def build_request(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolSpec],
    ) -> dict[str, Any]:
        """``client.beta.messages.create`` に渡す引数を組み立てる（試験で中身を確かめる）。"""
        tool_defs: list[dict[str, Any]] = [
            {"name": t.name, "description": t.description, "input_schema": dict(t.input_schema)}
            for t in sorted(tools, key=lambda t: t.name)
        ]
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.effort},
            # 前置き（tools → system）の末尾に明示の区切り。会話の末尾は自動キャッシュ。
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "cache_control": {"type": "ephemeral"},
            "tools": tool_defs,
            "messages": list(messages),
        }

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolSpec],
    ) -> LLMTurn:
        request = self.build_request(system=system, messages=messages, tools=tools)
        try:
            response = await self._client.beta.messages.create(**request)
        except anthropic.APIError as e:
            raise to_llm_error(e) from e
        except anthropic.CredentialsError as e:
            raise LLMError(f"Claude API の認証情報を読み込めません: {e}", kind="credentials") from e
        except TypeError as e:
            # 認証情報が無いとき、SDK は要求を送る前のヘッダの検査で TypeError を送出する
            if not _raised_by_header_check(e):
                raise
            raise LLMError(
                "Claude API の認証情報が見つかりません（ANTHROPIC_API_KEY などを設定してください）",
                kind="credentials",
            ) from e
        return to_turn(response, requested_model=self.model)


#: 時間をおけば直りうる HTTP の誤り（レート制限・過負荷・サーバの一時的な誤り）。
_TRANSIENT_STATUS_ERRORS: tuple[type[anthropic.APIStatusError], ...] = (
    anthropic.RateLimitError,
    anthropic.OverloadedError,
    anthropic.ServiceUnavailableError,
    anthropic.DeadlineExceededError,
    anthropic.InternalServerError,
)


def to_llm_error(e: anthropic.APIError) -> LLMError:
    """SDK の例外を、型で分類した :class:`LLMError` にする（文面では判定しない）。"""
    if isinstance(e, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return LLMError(
            f"Claude API の認証に失敗しました（HTTP {e.status_code}）: {e}", kind="auth"
        )
    if isinstance(e, _TRANSIENT_STATUS_ERRORS):
        return LLMError(
            f"Claude API が一時的なエラーを返しました（HTTP {e.status_code}）: {e}",
            kind="transient",
        )
    if isinstance(e, anthropic.APIStatusError):
        return LLMError(f"Claude API がエラーを返しました（HTTP {e.status_code}）: {e}")
    if isinstance(e, anthropic.APIConnectionError):  # 時間切れ（APITimeoutError）を含む
        return LLMError(f"Claude API に接続できませんでした: {e}", kind="transient")
    return LLMError(f"Claude API の呼び出しに失敗しました: {e}")


def _raised_by_header_check(e: TypeError) -> bool:
    """SDK の認証ヘッダの検査（``_validate_headers``）が送出した TypeError か。"""
    tb = e.__traceback__
    names = []
    while tb is not None:
        names.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    return "_validate_headers" in names


def to_turn(response: Any, *, requested_model: str) -> LLMTurn:
    """SDK の応答を正規化する。``content`` は加工せずに ``raw_content`` に入れる。"""
    content = list(response.content or [])
    texts = tuple(b.text for b in content if getattr(b, "type", None) == "text")
    tool_uses = tuple(
        ToolUse(id=b.id, name=b.name, input=dict(b.input or {}))
        for b in content
        if getattr(b, "type", None) == "tool_use"
    )
    usage = normalize_usage(_dump(response.usage))
    model = getattr(response, "model", None) or requested_model
    stop_details = getattr(response, "stop_details", None)
    return LLMTurn(
        texts=texts,
        tool_uses=tool_uses,
        stop_reason=str(response.stop_reason or "end_turn"),
        usage=usage,
        raw_content=content,
        model=model,
        charges=_charges(response.usage, model, usage),
        stop_details=_dump(stop_details) if stop_details is not None else None,
    )


def _charges(raw_usage: Any, model: str, usage: Mapping[str, int]) -> tuple[Charge, ...]:
    """課金の内訳。フォールバックが動いたときは試行ごと（``usage.iterations``）に分ける。

    最上位の ``usage`` は回答を作った試行の分しか含まないため。
    """
    iterations = getattr(raw_usage, "iterations", None) or []
    if any(getattr(it, "type", None) == "fallback_message" for it in iterations):
        return tuple(
            Charge(model=getattr(it, "model", None) or model, usage=normalize_usage(_dump(it)))
            for it in iterations
            if getattr(it, "type", None) in ("message", "fallback_message")
        )
    return (Charge(model=model, usage=usage),)


def _dump(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    return obj.model_dump(mode="json")
