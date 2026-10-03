"""コアの部品どうし（ゲートウェイ・検証器・Agent）と、ツールサービスとの契約（ADR-0008）。

ここにはデータの形と境界の約束だけを置き、処理は置かない。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# ツール名
# ---------------------------------------------------------------------------

#: ドメインで宣言するツール名（例 ``damage.expected``）。
DOMAIN_TOOL_NAME = re.compile(r"^[a-z_]+(\.[a-z_]+)+$")


def to_wire_name(domain_name: str) -> str:
    """ドメインのツール名を、MCP・LLM に渡す名前に変える（``.`` → ``_``）。

    Claude API のツール名は ``^[a-zA-Z0-9_-]{1,64}$`` で ``.`` を使えないため。
    """
    if not DOMAIN_TOOL_NAME.match(domain_name):
        raise ValueError(f"ツール名の形式が不正です: {domain_name}")
    return domain_name.replace(".", "_")


# ---------------------------------------------------------------------------
# ツールサービスの結果（MCP のテキスト内容として JSON で返る）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolEnvelope:
    """ツールサービスが返す結果の形（JSON の 1 オブジェクト）。

    JSON の例::

        {"tool": "damage.expected",
         "values": {"total": "6192.000000", "base": "5000.000000"},
         "unverified_inputs": ["gacha_rules:featured-character"],
         "data_version": "v2.x"}

    - ``values`` の値は 10 進数の文字列（``BigDecimal.toPlainString()`` 相当）。
      浮動小数点の誤差を持ち込まない。
    - ``unverified_inputs`` は計算に使った未確認データの ID（``<データファイル名>:<項目 ID>``）。
      無ければ空（ADR-0006）。
    - ``data_version`` はデータを参照しなかった場合 ``None``。
    """

    tool: str
    values: Mapping[str, Decimal]
    unverified_inputs: tuple[str, ...] = ()
    data_version: str | None = None

    @staticmethod
    def from_json(doc: Mapping[str, Any]) -> ToolEnvelope:
        return ToolEnvelope(
            tool=str(doc["tool"]),
            values={k: Decimal(str(v)) for k, v in doc["values"].items()},
            unverified_inputs=tuple(doc.get("unverified_inputs") or ()),
            data_version=doc.get("data_version"),
        )


class ToolBackend(Protocol):
    """1 つのツールサービス（例 calc-engine）への接続。MCP の実装とテスト用の偽物がある。"""

    async def list_tools(self) -> list[ToolSpec]:
        """サービスが公開するツール（名前は wire 名）。"""
        ...

    async def call_tool(self, wire_name: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        """ツールを呼ぶ。入力の誤りは :class:`ToolError` を送出する。"""
        ...

    async def aclose(self) -> None: ...


class ToolError(Exception):
    """ツールが入力を拒否した、または計算できなかった。LLM には is_error の結果として返す。"""


# ---------------------------------------------------------------------------
# ゲートウェイが LLM に見せるツールと、呼び出しの結果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """LLM に渡すツール定義。``name`` は wire 名、``input_schema`` は JSON Schema。"""

    name: str
    description: str
    input_schema: Mapping[str, Any]


#: 出典 ID。``<呼び出し ID>.<フィールド>``（例 ``c1.total``）。
#: 呼び出し ID はゲートウェイが 1 回の質問の中で振る。
SOURCE_ID = re.compile(r"^c[0-9]+\.[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class SourceValue:
    """出典 ID が指す 1 つの値。"""

    source_id: str
    value: Decimal
    tool: str
    unverified_inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CallOutcome:
    """ゲートウェイ経由の 1 回の呼び出しの結果。"""

    call_id: str
    tool: str
    arguments: Mapping[str, Any]
    sources: tuple[SourceValue, ...] = ()
    error: str | None = None

    def for_llm(self) -> dict[str, Any]:
        """LLM の tool_result に入れる内容。

        値は出典 ID と並べて渡し、回答ではプレースホルダで引用させる。
        """
        if self.error is not None:
            return {"call_id": self.call_id, "error": self.error}
        return {
            "call_id": self.call_id,
            "values": {s.source_id: str(s.value) for s in self.sources},
            "unverified": sorted({u for s in self.sources for u in s.unverified_inputs}),
        }


class BudgetExceeded(Exception):
    """コストの上限（日次・月次）に達したため、LLM を呼べない。"""

    def __init__(
        self,
        message: str,
        *,
        period: str | None = None,
        spent: Decimal | None = None,
        cap: Decimal | None = None,
    ) -> None:
        """
        :param period: 達した上限（``daily`` か ``monthly``）。
        :param spent: その期間の使用額（USD）。
        :param cap: その期間の上限（USD）。
        """
        super().__init__(message)
        self.period = period
        self.spent = spent
        self.cap = cap


# ---------------------------------------------------------------------------
# 回答のテンプレートとプレースホルダ（ADR-0005・ADR-0008）
# ---------------------------------------------------------------------------

#: 回答中のプレースホルダ。``[[c1.total]]``、
#: または書式付きの ``[[c1.total|0]]``・``[[c2.ratio|%1]]``。
#: 書式：省略＝小数 2 桁まで（末尾の 0 は落とす）、``N``＝小数 N 桁、
#: ``%N``＝100 倍して小数 N 桁 + ``%``。
#: 整数部は 3 桁ごとに ``,`` で区切る。丸めは ROUND_HALF_EVEN。
PLACEHOLDER = re.compile(r"\[\[(?P<source>c[0-9]+\.[a-z][a-z0-9_]*)(?:\|(?P<fmt>%?[0-9]))?\]\]")

#: 未確認データに由来する値を引用した回答に、レンダラが付ける注記（ADR-0006）。
UNVERIFIED_NOTE = "※ この回答の数値の一部は、未確認のサンプルデータに基づいています。"


@dataclass(frozen=True)
class Verdict:
    """検証器の判定。``ok`` のとき ``rendered`` に利用者へ返す文が入る。"""

    ok: bool
    problems: tuple[str, ...] = ()
    rendered: str | None = None
    cited: tuple[str, ...] = field(default=())
