"""台本どおりに応答する LLM（テスト・CI・評価の再現用）。API キーを使わない。

台本は応答の列。各応答の形（YAML でも dict でもよい）::

    - tool_uses:                       # 省略可。あれば stop_reason は既定で tool_use
        - {name: damage_expected, input: {atk: 2000, ...}}   # id は省略可
      text: "計算します。"             # 省略可
    - text: "期待ダメージは [[c1.total|0]] です。"
      expect: "差し戻し"               # 省略可。直前の利用者メッセージに含まれるべき文字列
      usage: {input_tokens: 1200, output_tokens: 80}         # 省略可（既定 0）
      stop_reason: end_turn            # 省略可（refusal・max_tokens も書ける）

台本より多く呼ばれたら :class:`ScriptExhausted` を送出する（想定外の往復を見逃さない）。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from core.agent.llm.base import Charge, LLMTurn, ToolUse, normalize_usage
from core.agent.llm.claude import DEFAULT_MODEL
from core.contracts import ToolSpec


class ScriptExhausted(AssertionError):
    """台本の応答を使い切った後に、さらに呼ばれた。"""


class ScriptMismatch(AssertionError):
    """台本の ``expect`` が、実際の履歴と合わなかった。"""


class ScriptedLLM:
    """台本の応答を順に返す。受け取った要求は :attr:`calls` に残す（試験で確かめる）。"""

    def __init__(self, turns: Sequence[Mapping[str, Any]], *, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._turns = [dict(t) for t in turns]
        self._next = 0
        self._tool_seq = 0
        #: 呼び出しごとの (system, messages の複製, tools)
        self.calls: list[dict[str, Any]] = []

    @classmethod
    def from_file(cls, path: Path | str, **kwargs: Any) -> ScriptedLLM:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        turns = doc["turns"] if isinstance(doc, Mapping) else doc
        return cls(turns, **kwargs)

    @property
    def remaining(self) -> int:
        return len(self._turns) - self._next

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolSpec],
    ) -> LLMTurn:
        # 履歴は後で追記されるので、呼ばれた時点の内容を複製して残す
        self.calls.append(
            {
                "system": system,
                "messages": json.loads(json.dumps(list(messages), default=str)),
                "tools": list(tools),
            }
        )
        if self._next >= len(self._turns):
            raise ScriptExhausted(
                f"台本の応答（{len(self._turns)} 件）を使い切った後に呼ばれました"
            )
        spec = self._turns[self._next]
        self._next += 1
        self._check_expect(spec, messages)
        return self._to_turn(spec)

    def _check_expect(self, spec: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]) -> None:
        expected = spec.get("expect")
        if not expected:
            return
        last = json.dumps(messages[-1]["content"], ensure_ascii=False, default=str)
        if str(expected) not in last:
            raise ScriptMismatch(f"直前のメッセージに {expected!r} がありません: {last[:300]}")

    def _to_turn(self, spec: Mapping[str, Any]) -> LLMTurn:
        content: list[dict[str, Any]] = []
        text = spec.get("text")
        if text:
            content.append({"type": "text", "text": str(text)})
        uses: list[ToolUse] = []
        for tu in spec.get("tool_uses") or ():
            self._tool_seq += 1
            use = ToolUse(
                id=str(tu.get("id") or f"toolu_scripted_{self._tool_seq:02d}"),
                name=str(tu["name"]),
                input=dict(tu.get("input") or {}),
            )
            uses.append(use)
            content.append(
                {"type": "tool_use", "id": use.id, "name": use.name, "input": dict(use.input)}
            )
        stop_reason = str(spec.get("stop_reason") or ("tool_use" if uses else "end_turn"))
        usage = normalize_usage(spec.get("usage"))
        return LLMTurn(
            texts=(str(text),) if text else (),
            tool_uses=tuple(uses),
            stop_reason=stop_reason,
            usage=usage,
            raw_content=content,
            model=self.model,
            charges=(Charge(model=self.model, usage=usage),),
            stop_details=spec.get("stop_details"),
        )
