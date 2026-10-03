"""LLM の抽象層。Agent はこの Protocol だけを知り、実物（Claude）と台本（テスト）を差し替える。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.contracts import ToolSpec

#: 使用量の辞書のキー（Budget.record に渡す形）。
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def normalize_usage(raw: Mapping[str, Any] | None) -> dict[str, int]:
    """使用量を 4 つのキーの整数にそろえる（欠けている・None のものは 0）。"""
    raw = raw or {}
    return {k: int(raw.get(k) or 0) for k in USAGE_KEYS}


@dataclass(frozen=True)
class ToolUse:
    """LLM が求めた 1 つのツール呼び出し。"""

    id: str
    name: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class Charge:
    """課金の単位（1 回の推論）。サーバ側のフォールバックが動くと 1 応答に複数ある。"""

    model: str
    usage: Mapping[str, int]


@dataclass(frozen=True)
class LLMTurn:
    """正規化した 1 回の応答。

    ``raw_content`` は履歴にそのまま追記する内容（応答のブロックを加工しない。
    思考ブロックや署名を保つため）。
    """

    texts: tuple[str, ...]
    tool_uses: tuple[ToolUse, ...]
    stop_reason: str
    usage: Mapping[str, int]
    raw_content: Sequence[Any]
    model: str
    charges: tuple[Charge, ...] = field(default=())
    stop_details: Mapping[str, Any] | None = None

    @property
    def text(self) -> str:
        return "".join(self.texts)


#: :class:`LLMError` の分類（利用者に返す回答の文面を選ぶのに使う）。
#: ``credentials``：認証情報が無い。``auth``：認証・権限の誤り（HTTP 401・403）。
#: ``transient``：レート制限・過負荷・サーバの一時的な誤り・通信の失敗（時間をおけば直りうる）。
#: ``other``：それ以外（要求の誤りなど）。
LLM_ERROR_KINDS = ("credentials", "auth", "transient", "other")


class LLMError(Exception):
    """LLM の呼び出しに失敗した（通信・認証・API の誤りなど。SDK の再試行の後）。"""

    def __init__(self, message: str, *, kind: str = "other") -> None:
        if kind not in LLM_ERROR_KINDS:
            raise ValueError(f"未知の LLMError の分類です: {kind}")
        super().__init__(message)
        self.kind = kind


class LLM(Protocol):
    """Agent から見た LLM。"""

    #: 既定のモデル ID（費用の計算とトレースに使う）。
    model: str

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolSpec],
    ) -> LLMTurn:
        """履歴（``messages``）の続きを 1 回生成する。履歴は書き換えない。"""
        ...
