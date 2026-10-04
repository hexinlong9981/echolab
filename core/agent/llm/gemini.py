"""Google Cloud Vertex AI（Gemini）による LLM の実装。

要求の組み立て（ADR-0008 と、利用者の決定に従う）:

- モデルは既定で ``gemini-2.5-flash``（費用が極めて低く、高速でツール呼び出しの精度が高い）。
  ``gemini-2.5-pro`` や ``gemini-1.5-flash`` も選択可能。
- 認証は Google Cloud の Application Default Credentials（ADC）または環境変数を使い、
  GCP の無料トライアル枠を活用する。
- 自動関数呼び出し（AFC）は無効化し、エージェントループが決定論的にツール実行を仲介する。
- 思考ブロック（``thought=True``）は ``turn.texts`` から除外して検証器が内部推論の数値を
  拾わないようにしつつ、履歴（``raw_content``）には思考署名を含めて保持する。
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from google import genai
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors, types

from core.agent.llm.base import Charge, LLMError, LLMTurn, ToolUse, normalize_usage
from core.contracts import ToolSpec

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_LOCATION = "us-central1"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.0


class GeminiLLM:
    """Vertex AI 上の Gemini API を呼ぶ LLM。"""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        project: str | None = None,
        location: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._seq = 0
        self._tool_call_names: dict[str, str] = {}

        if client is not None:
            self._client = client
        else:
            proj = (
                project
                or os.environ.get("GCP_PROJECT_ID")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
            )
            loc = (
                location
                or os.environ.get("GCP_REGION")
                or os.environ.get("GOOGLE_CLOUD_LOCATION")
                or DEFAULT_LOCATION
            )
            if not proj:
                try:
                    import google.auth

                    _, proj = google.auth.default()
                except Exception:
                    pass
            self._client = genai.Client(vertexai=True, project=proj, location=loc)

    def _next_call_id(self, name: str) -> str:
        self._seq += 1
        return f"call_{name}_{self._seq:02d}"

    def build_tools(self, tools: Sequence[ToolSpec]) -> list[types.Tool]:
        """ToolSpec のリストを Gemini の Tool 定義に変換する（名前順で整列）。"""
        if not tools:
            return []
        decls = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema=dict(t.input_schema),
            )
            for t in sorted(tools, key=lambda t: t.name)
        ]
        return [types.Tool(function_declarations=decls)]

    def build_contents(self, messages: Sequence[Mapping[str, Any]]) -> list[types.Content]:
        """エージェントループの履歴を Gemini の Content リストに変換する。"""
        contents: list[types.Content] = []
        for msg in messages:
            role = msg.get("role")
            raw = msg.get("content")
            if role == "user":
                if isinstance(raw, str):
                    contents.append(
                        types.Content(role="user", parts=[types.Part.from_text(text=raw)])
                    )
                elif isinstance(raw, list):
                    # ツール実行結果のブロック
                    parts: list[types.Part] = []
                    for block in raw:
                        if not isinstance(block, Mapping):
                            continue
                        tool_use_id = str(block.get("tool_use_id") or "")
                        tool_name = self._tool_call_names.get(tool_use_id)
                        if not tool_name:
                            # ID から名前を復元するか、ID そのものをフォールバックにする
                            if tool_use_id.startswith("call_"):
                                segments = tool_use_id.split("_")
                                if len(segments) >= 3:
                                    tool_name = "_".join(segments[1:-1])
                                else:
                                    tool_name = tool_use_id
                            else:
                                tool_name = tool_use_id

                        content_val = block.get("content")
                        if isinstance(content_val, str):
                            try:
                                resp_dict = json.loads(content_val)
                            except (json.JSONDecodeError, ValueError):
                                resp_dict = {"output": content_val}
                        elif isinstance(content_val, Mapping):
                            resp_dict = dict(content_val)
                        else:
                            resp_dict = {"output": str(content_val)}

                        if not isinstance(resp_dict, Mapping):
                            resp_dict = {"output": resp_dict}

                        if block.get("is_error"):
                            resp_dict = dict(resp_dict)
                            resp_dict.setdefault("is_error", True)

                        part = types.Part.from_function_response(
                            name=tool_name,
                            response=resp_dict,
                        )
                        if tool_use_id and hasattr(part, "function_response"):
                            with contextlib.suppress(Exception):
                                part.function_response.id = tool_use_id
                        parts.append(part)
                    if parts:
                        contents.append(types.Content(role="user", parts=parts))
            elif role == "assistant":
                if isinstance(raw, types.Content):
                    contents.append(raw)
                elif hasattr(raw, "parts"):
                    contents.append(types.Content(role="model", parts=list(raw.parts)))
                elif isinstance(raw, list):
                    parts = []
                    for item in raw:
                        if isinstance(item, types.Part):
                            parts.append(item)
                        elif isinstance(item, Mapping):
                            item_type = item.get("type")
                            if item_type == "text" and item.get("text"):
                                parts.append(types.Part.from_text(text=str(item["text"])))
                            elif item_type == "tool_use":
                                parts.append(
                                    types.Part.from_function_call(
                                        name=str(item["name"]),
                                        args=dict(item.get("input") or {}),
                                    )
                                )
                    if parts:
                        contents.append(types.Content(role="model", parts=parts))
                elif isinstance(raw, str):
                    contents.append(
                        types.Content(role="model", parts=[types.Part.from_text(text=raw)])
                    )
        return contents

    def build_request(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[ToolSpec],
    ) -> dict[str, Any]:
        """generate_content に渡す引数を組み立てる。"""
        tool_list = self.build_tools(tools)
        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            tools=tool_list if tool_list else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
        contents = self.build_contents(messages)
        return {
            "model": self.model,
            "contents": contents,
            "config": config,
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
            response = await self._client.aio.models.generate_content(**request)
        except DefaultCredentialsError as e:
            msg = f"Google Cloud の認証情報を読み込めません: {e}"
            raise LLMError(msg, kind="credentials") from e
        except errors.APIError as e:
            raise to_llm_error(e) from e
        except Exception as e:
            raise to_llm_error(e) from e
        return self.to_turn(response, requested_model=self.model)

    def to_turn(self, response: Any, *, requested_model: str) -> LLMTurn:
        """SDK の応答を LLMTurn に正規化する。思考ブロックは本文から除外する。"""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return LLMTurn(
                texts=(),
                tool_uses=(),
                stop_reason="refusal",
                usage=normalize_usage({}),
                raw_content=[],
                model=requested_model,
                charges=(Charge(model=requested_model, usage=normalize_usage({})),),
            )

        candidate = candidates[0]
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []

        # 思考ブロック（thought=True）を除外して回答本文を取り出す
        texts = tuple(
            str(p.text)
            for p in parts
            if getattr(p, "text", None) and not getattr(p, "thought", False)
        )

        uses: list[ToolUse] = []
        for p in parts:
            fc = getattr(p, "function_call", None)
            if fc is not None:
                fc_id = getattr(fc, "id", None) or self._next_call_id(fc.name)
                self._tool_call_names[fc_id] = fc.name
                uses.append(
                    ToolUse(
                        id=fc_id,
                        name=fc.name,
                        input=dict(getattr(fc, "args", None) or {}),
                    )
                )

        finish_reason = getattr(candidate, "finish_reason", None)
        finish_str = str(finish_reason).upper() if finish_reason else ""
        if any(
            bad in finish_str
            for bad in ("SAFETY", "BLOCKLIST", "PROHIBITED", "SPII", "IMAGE_SAFETY")
        ):
            stop_reason = "refusal"
        elif "MAX_TOKENS" in finish_str:
            stop_reason = "max_tokens"
        elif uses:
            stop_reason = "tool_use"
        else:
            stop_reason = "end_turn"

        usage_meta = getattr(response, "usage_metadata", None)
        raw_usage = {
            "input_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage_meta, "candidates_token_count", 0) or 0,
            "cache_read_input_tokens": getattr(usage_meta, "cached_content_token_count", 0) or 0,
            "cache_creation_input_tokens": 0,
        }
        usage = normalize_usage(raw_usage)
        model = getattr(response, "model_version", None) or requested_model

        return LLMTurn(
            texts=texts,
            tool_uses=tuple(uses),
            stop_reason=stop_reason,
            usage=usage,
            raw_content=content if content is not None else parts,
            model=model,
            charges=(Charge(model=requested_model, usage=usage),),
            stop_details={"finish_reason": finish_str} if finish_str else None,
        )


def to_llm_error(e: Exception) -> LLMError:
    """SDK の例外を分類した LLMError に変換する。"""
    if isinstance(e, DefaultCredentialsError):
        return LLMError(f"Google Cloud の認証情報が見つかりません: {e}", kind="credentials")
    if isinstance(e, errors.APIError):
        code = getattr(e, "code", None)
        if code in (401, 403):
            return LLMError(
                f"Vertex AI API の認証・権限エラーです（HTTP {code}）: {e}", kind="auth"
            )
        if code in (429, 500, 502, 503, 504):
            return LLMError(
                f"Vertex AI API が一時的なエラーを返しました（HTTP {code}）: {e}",
                kind="transient",
            )
        return LLMError(f"Vertex AI API がエラーを返しました（HTTP {code}）: {e}", kind="other")
    return LLMError(f"Vertex AI API の呼び出しに失敗しました: {e}", kind="other")
