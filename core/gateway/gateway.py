"""ゲートウェイ：LLM とツールサービスの間に立つ唯一の入口（ADR-0008）。

- 許可リスト：``domain.yaml`` で宣言したツールだけを見せ、呼ばせる（既定拒否）。
- 入力の検査：サービスが公開する入力スキーマ（JSON Schema）で、呼ぶ前に検査する。
- 採番：呼び出し ID（``c1``・``c2``…）と出典 ID（``c1.total``）を 1 回の質問の中で振る。
- 比較ツール（``compare.*``、ADR-0005）はコアで計算し、入力の出典 ID をここで値に解決する。
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from core.compare import COMPARE_SPECS, COMPARE_TOOLS
from core.contracts import (
    SOURCE_ID,
    CallOutcome,
    SourceValue,
    ToolBackend,
    ToolEnvelope,
    ToolError,
    ToolSpec,
    to_wire_name,
)
from core.gateway.budget import Budget
from core.gateway.mcp_backend import McpStdioBackend


@dataclass(frozen=True)
class _Route:
    """wire 名から、ドメインのツール名・サービス・検査器への対応。"""

    tool: str
    spec: ToolSpec
    validator: Draft202012Validator
    backend: ToolBackend | None  # None は比較ツール（コアで計算）


class UnknownDomainError(ValueError):
    """指定したドメインパック（``domains/<domain>/domain.yaml``）が無い。"""


class ContextError(ValueError):
    """利用者が指定する項目（``domain.yaml`` の ``user_context``）が、ドメインの宣言と合わない。"""


def available_domains(repo_root: Path) -> list[str]:
    """使えるドメイン（``domains/*/domain.yaml`` があるディレクトリ名）。"""
    return sorted(p.parent.name for p in (Path(repo_root) / "domains").glob("*/domain.yaml"))


def load_domain(repo_root: Path, domain: str) -> dict[str, Any]:
    """``domains/<domain>/domain.yaml`` を読む。ドメインの有無はここだけで確かめる。

    :raises UnknownDomainError: ドメインが無いとき（使えるドメインをメッセージに含める）。
    """
    path = Path(repo_root) / "domains" / domain / "domain.yaml"
    if not domain or "/" in domain or "\\" in domain or not path.is_file():
        known = "、".join(available_domains(repo_root)) or "（なし）"
        raise UnknownDomainError(f"ドメインが見つかりません: {domain}（使えるドメイン: {known}）")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Gateway:
    """1 回の質問（セッション）ごとに開くゲートウェイ。``async with`` でも使える。"""

    def __init__(
        self,
        routes: Mapping[str, _Route],
        backends: Mapping[str, ToolBackend],
        budget: Budget,
        context: Mapping[str, Any] | None = None,
        user_context: tuple[str, ...] = (),
    ) -> None:
        self._routes = dict(routes)
        self._context = dict(context or {})
        self._user_context = tuple(user_context)
        self._backends = dict(backends)
        self._counter = itertools.count(1)
        self._sources: dict[str, SourceValue] = {}
        self._closed = False
        self.budget = budget

    @classmethod
    async def open(
        cls,
        repo_root: Path,
        domain: str,
        *,
        backends: Mapping[str, ToolBackend] | None = None,
        budget: Budget | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> Gateway:
        """ドメインのツールを使えるゲートウェイを開く。

        :param backends: サービス名 → 接続の差し替え（試験用）。無いサービスは
            ``config/services.yaml`` に従って :class:`McpStdioBackend` で起動する。
        :param budget: 省略時は ``config/budget.yaml`` から作る。
        :param context: 利用者が指定する項目（例 ``{"progress": "novel:5"}``）。ドメインが
            ``domain.yaml`` の ``user_context`` で宣言した名前だけ受け付ける。LLM には見せず、
            ドメインのツールを呼ぶときにゲートウェイが入力に加える（LLM は値を変えられない）。
        :raises ContextError: 宣言されていない項目を指定したとき。
        """
        repo_root = Path(repo_root)
        manifest = load_domain(repo_root, domain)
        user_context = tuple(manifest.get("user_context") or ())
        context = dict(context or {})
        undeclared = sorted(set(context) - set(user_context))
        if undeclared:
            accepted = "、".join(user_context) or "（なし）"
            raise ContextError(
                f"ドメイン {domain} は利用者の指定 {', '.join(undeclared)} を受け付けません"
                f"（受け付ける項目: {accepted}）"
            )
        declared: dict[str, str] = {}  # wire 名 → ドメインのツール名
        services: dict[str, str] = {}  # ドメインのツール名 → サービス名
        descriptions: dict[str, str] = {}
        for t in manifest.get("tools") or []:
            name = t["name"]
            if name in COMPARE_TOOLS:
                raise ValueError(f"{name} はコアの比較ツールのため、ドメインでは宣言できません")
            declared[to_wire_name(name)] = name
            services[name] = t["service"]
            descriptions[name] = t.get("description", "")

        overrides = dict(backends or {})
        started: dict[str, ToolBackend] = {}
        try:
            for service in dict.fromkeys(services.values()):
                if service in overrides:
                    started[service] = overrides[service]
                else:
                    started[service] = await McpStdioBackend.for_service(repo_root, service)

            routes: dict[str, _Route] = {}
            for service, backend in started.items():
                for spec in await backend.list_tools():
                    tool = declared.get(spec.name)
                    # 既定拒否：宣言の無いツールと、別サービスの宣言のツールは見せない
                    if tool is None or services[tool] != service:
                        continue
                    if not spec.description:
                        spec = ToolSpec(spec.name, descriptions[tool], spec.input_schema)
                    # 利用者が指定する項目は LLM に見せない（LLM が送っても入力の検査で拒む）
                    spec = _hide_properties(spec, user_context)
                    routes[spec.name] = _Route(tool, spec, _validator(spec), backend)
            for spec in COMPARE_SPECS:
                tool = next(t for t in COMPARE_TOOLS if to_wire_name(t) == spec.name)
                routes[spec.name] = _Route(tool, spec, _validator(spec), None)
            if budget is None:
                budget = Budget.from_config(repo_root)
        except BaseException:
            for backend in started.values():
                await backend.aclose()
            raise
        return cls(routes, started, budget, context=context, user_context=user_context)

    async def aclose(self) -> None:
        """サービスへの接続を閉じる。何度呼んでもよい。"""
        if self._closed:
            return
        self._closed = True
        for backend in self._backends.values():
            await backend.aclose()

    async def __aenter__(self) -> Gateway:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------

    def tool_specs(self) -> list[ToolSpec]:
        """LLM に渡すツール定義（ドメインのツールのうちサービスが公開するもの + 比較ツール）。"""
        return [r.spec for r in self._routes.values()]

    @property
    def context(self) -> Mapping[str, Any]:
        """利用者が指定した項目（トレースに残す）。"""
        return dict(self._context)

    @property
    def sources(self) -> Mapping[str, SourceValue]:
        """このセッションで発行した出典 ID → 値。"""
        return dict(self._sources)

    async def call(self, wire_name: str, arguments: Mapping[str, Any]) -> CallOutcome:
        """ツールを呼ぶ。ツールの誤り・入力の誤りは例外ではなく ``error`` 付きの結果で返す。"""
        # await の前に採番するので、並行に呼んでも ID は重複しない
        call_id = f"c{next(self._counter)}"
        arguments = dict(arguments)
        route = self._routes.get(wire_name)
        if route is None:
            return CallOutcome(
                call_id,
                wire_name,
                arguments,
                error=f"ツール {wire_name} は使えません（このドメインで許可されていません）",
            )
        if self._closed:
            return CallOutcome(call_id, route.tool, arguments, error="ゲートウェイは閉じています")

        overridden = sorted(k for k in self._user_context if k in arguments)
        if route.backend is not None and overridden:
            # サービスのスキーマに関係なく拒む（利用者の指定を LLM が書き換えられないように）
            return CallOutcome(
                call_id,
                route.tool,
                arguments,
                error=f"{', '.join(overridden)} は利用者が指定する項目のため、指定できません",
            )

        errors = sorted(route.validator.iter_errors(arguments), key=lambda e: list(e.path))
        if errors:
            detail = "; ".join(_describe(e) for e in errors)
            return CallOutcome(call_id, route.tool, arguments, error=f"入力が不正です: {detail}")

        try:
            if route.backend is None:
                envelope = self._compare(route.tool, arguments)
            else:
                envelope = await route.backend.call_tool(wire_name, self._with_context(arguments))
                if envelope.tool != route.tool:
                    raise ToolError(
                        f"ツールの結果の名前が一致しません: {envelope.tool}（期待 {route.tool}）"
                    )
            sources = tuple(_to_source(call_id, envelope, f) for f in envelope.values)
        except ToolError as e:
            return CallOutcome(call_id, route.tool, arguments, error=str(e))

        for s in sources:
            self._sources[s.source_id] = s
        return CallOutcome(
            call_id, route.tool, arguments, sources=sources, texts=dict(envelope.texts)
        )

    def _with_context(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """ドメインのツールの入力に、利用者が指定した項目を加える。

        :raises ToolError: ドメインが宣言した項目を利用者が指定していないとき。
        """
        missing = [name for name in self._user_context if name not in self._context]
        if missing:
            raise ToolError(
                f"利用者が指定する項目 {', '.join(missing)} がありません"
                f"（CLI では --context {missing[0]}=… で指定します）。利用者に尋ねてください"
            )
        return {**arguments, **{k: self._context[k] for k in self._user_context}}

    def _compare(self, tool: str, arguments: Mapping[str, Any]) -> ToolEnvelope:
        inputs: list[SourceValue] = []
        for key in ("a", "b"):
            source = self._sources.get(arguments[key])
            if source is None:
                raise ToolError(
                    f"{key} の出典 ID「{arguments[key]}」はこの質問のツール結果にありません"
                )
            inputs.append(source)
        a, b = inputs
        values: dict[str, Decimal] = COMPARE_TOOLS[tool](a.value, b.value)
        unverified = tuple(dict.fromkeys(a.unverified_inputs + b.unverified_inputs))
        return ToolEnvelope(tool=tool, values=values, unverified_inputs=unverified)


def _hide_properties(spec: ToolSpec, names: tuple[str, ...]) -> ToolSpec:
    """入力スキーマから、利用者が指定する項目を除く（LLM に渡す定義と、入力の検査に使う）。"""
    schema = dict(spec.input_schema)
    props = dict(schema.get("properties") or {})
    if not names or not any(n in props for n in names):
        return spec
    for n in names:
        props.pop(n, None)
    schema["properties"] = props
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r not in names]
    return ToolSpec(spec.name, spec.description, schema)


def _validator(spec: ToolSpec) -> Draft202012Validator:
    schema = dict(spec.input_schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        raise ValueError(f"ツール {spec.name} の入力スキーマが不正です: {e.message}") from e
    return Draft202012Validator(schema)


def _describe(error: Any) -> str:
    """入力の検査の誤りを日本語で説明する（よく使う検査だけ。ほかは jsonschema の文のまま）。"""
    where = "/".join(str(p) for p in error.absolute_path) or "(全体)"
    return f"{where}: {_describe_message(error)}"


_TYPE_NAMES = {
    "object": "オブジェクト",
    "array": "配列",
    "string": "文字列",
    "number": "数値",
    "integer": "整数",
    "boolean": "真偽値",
    "null": "null",
}


def _describe_message(error: Any) -> str:
    v, expected, instance = error.validator, error.validator_value, error.instance
    if v == "required":
        missing = [k for k in expected if isinstance(instance, Mapping) and k not in instance]
        return f"必須の項目がありません: {', '.join(missing) or ', '.join(expected)}"
    if v == "type":
        names = [expected] if isinstance(expected, str) else list(expected)
        shown = "・".join(_TYPE_NAMES.get(n, n) for n in names)
        return f"{_show(instance)} は{shown}ではありません"
    if v == "minimum":
        return f"{_show(instance)} は最小値 {expected} より小さい値です"
    if v == "maximum":
        return f"{_show(instance)} は最大値 {expected} より大きい値です"
    if v == "exclusiveMinimum":
        return f"{_show(instance)} は {expected} より大きい値である必要があります"
    if v == "exclusiveMaximum":
        return f"{_show(instance)} は {expected} より小さい値である必要があります"
    if v == "enum":
        return f"{_show(instance)} は使えない値です（使える値: {', '.join(map(_show, expected))}）"
    if v == "additionalProperties" and isinstance(instance, Mapping):
        known = set(error.schema.get("properties") or {})
        extra = sorted(k for k in instance if k not in known)
        if extra:
            return f"使えない項目があります: {', '.join(extra)}"
    if v == "pattern":
        return f"{_show(instance)} は形式（{expected}）に合いません"
    return error.message


def _show(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _to_source(call_id: str, envelope: ToolEnvelope, field: str) -> SourceValue:
    source_id = f"{call_id}.{field}"
    if not SOURCE_ID.fullmatch(source_id):
        raise ToolError(f"ツールの結果のフィールド名が不正です: {field}")
    return SourceValue(
        source_id=source_id,
        value=envelope.values[field],
        tool=envelope.tool,
        unverified_inputs=envelope.unverified_inputs,
    )
