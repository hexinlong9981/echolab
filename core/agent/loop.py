"""Agent の往復（ADR-0005・ADR-0008）。

質問 → LLM がツールを選ぶ → ゲートウェイで計算 → LLM が回答テンプレートを書く → 検証器 →
（不合格なら差し戻して書き直させる）→ レンダラが数値を埋めた回答。

LLM が数値を書く経路は無い。検証に通らない下書きが続いたら、数値を含まない定型の回答で終える。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from core.agent.llm.base import LLM, LLMError, LLMTurn, ToolUse
from core.contracts import BudgetExceeded, CallOutcome, SourceValue, ToolSpec, Verdict
from core.trace import DEFAULT_TRACE_DIR, TraceWriter

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

#: ツールを呼ぶ往復の上限（1 回の質問あたり）。
DEFAULT_MAX_TOOL_ROUNDS = 6
#: 検証に落ちた下書きを書き直させる回数の上限。
DEFAULT_MAX_RETRIES = 2

# 定型の回答。数字を含めない（検証を通らなかった場合にも数値を出さないため）。
FALLBACK_ANSWER = (
    "申し訳ありません。計算結果の出典を確かめられる回答を作れなかったため、数値を含む回答は控えます。"
    "条件を具体的にして、もう一度質問してください。"
)
BUDGET_ANSWER = (
    "コストの上限（日次または月次）に達したため、今は回答できません。"
    "上限が戻ってから、もう一度お試しください。"
)
#: 上限の種類ごとの説明（期間の名前・戻る時期・上書きする環境変数・設定のキー）。
_BUDGET_PERIODS = {
    "daily": ("今日（UTC）", "日次", "UTC の日付が変わると", "ECHOLAB_DAILY_USD", "caps_usd.daily"),
    "monthly": (
        "今月（UTC）",
        "月次",
        "UTC の月が変わると",
        "ECHOLAB_MONTHLY_USD",
        "caps_usd.monthly",
    ),
}
REFUSAL_ANSWER = "この質問には回答できませんでした（モデルの安全機能により応答が止まりました）。"
TRUNCATED_ANSWER = (
    "応答が長くなりすぎて途中で切れたため、回答を完成できませんでした。質問を分けてお試しください。"
)
TOOL_LIMIT_ANSWER = (
    "計算の手順が多くなりすぎたため、回答を完成できませんでした。質問を分けてお試しください。"
)
# LLM の呼び出しの失敗（LLMError.kind ごと）。原因と直し方を短く伝える。数字を含めない。
LLM_ERROR_ANSWERS = {
    "credentials": (
        "Claude API の認証情報が見つからないため、回答できませんでした。"
        "環境変数 ANTHROPIC_API_KEY を設定する（または ant auth login でログインする）か、"
        "API キーの要らない台本モード（--llm scripted）をお使いください。"
    ),
    "auth": (
        "Claude API の認証に失敗したため、回答できませんでした。"
        "ANTHROPIC_API_KEY（または ant auth login のログイン）が有効かを確かめてください。"
    ),
    "transient": (
        "Claude API が混み合っているか、接続できなかったため、回答できませんでした。"
        "時間をおいてお試しください。"
    ),
    "other": (
        "Claude API の呼び出しに失敗したため、回答できませんでした。"
        "詳細はトレースの llm_error の行を確かめてください。"
    ),
}
LLM_ERROR_ANSWER = LLM_ERROR_ANSWERS["other"]


class Budget(Protocol):
    def check(self) -> None: ...

    def record(self, model: str, usage: Mapping[str, int]) -> Decimal: ...


class GatewayLike(Protocol):
    """Agent が使うゲートウェイの面（``core.gateway.Gateway``）。"""

    budget: Budget

    @property
    def sources(self) -> Mapping[str, SourceValue]: ...

    def tool_specs(self) -> list[ToolSpec]: ...

    async def call(self, wire_name: str, args: Mapping[str, Any]) -> CallOutcome: ...


class Verifier(Protocol):
    def __call__(
        self, template: str, question: str, sources: Mapping[str, SourceValue]
    ) -> Verdict: ...


@dataclass(frozen=True)
class AgentResult:
    """1 回の質問の結果。"""

    #: 利用者に返す文（検証済みでレンダリングしたもの、または定型の回答）
    answer: str
    #: ``answered``・``fallback``・``budget_exceeded``・``refusal``・``max_tokens``・
    #: ``tool_round_limit``・``llm_error``
    status: str
    run_id: str
    trace_path: Path
    #: 最後の検証の判定（下書きが 1 つも無ければ None）
    verdict: Verdict | None = None
    #: 回答が引用した出典（``status == "answered"`` のときだけ）
    cited: tuple[SourceValue, ...] = ()
    cost_usd: Decimal = Decimal(0)
    drafts: int = 0
    drafts_rejected: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    #: 最後の下書き（テンプレート）。評価で使う
    template: str | None = None
    problems: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return self.status == "answered"


def budget_answer(e: BudgetExceeded) -> str:
    """コストの上限に達したときの回答。どの上限か・使用額と上限・変え方を伝える。

    金額はコストの台帳と設定から決まる値で、LLM が書いたものではない。
    """
    period = _BUDGET_PERIODS.get(e.period or "")
    if period is None or e.spent is None or e.cap is None:
        return BUDGET_ANSWER
    when, name, resets, env, key = period
    return (
        f"{when}のコストが{name}の上限に達したため、今は回答できません"
        f"（使用額 {e.spent} USD / 上限 {e.cap} USD）。"
        f"{resets}使えるようになります。"
        f"上限は環境変数 {env} か config/budget.yaml の {key} で変えられます。"
    )


def load_system_prompt(repo_root: Path, domain: str) -> str:
    """システムプロンプト = コアの規則 + ドメインのプロンプト（``prompts_dir/system.md``）。"""
    import yaml

    core = (PROMPTS_DIR / "core.md").read_text(encoding="utf-8").strip()
    domain_dir = repo_root / "domains" / domain
    manifest = yaml.safe_load((domain_dir / "domain.yaml").read_text(encoding="utf-8"))
    domain_prompt = domain_dir / manifest.get("prompts_dir", "prompts") / "system.md"
    parts = [core]
    if domain_prompt.is_file():
        parts.append(domain_prompt.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts) + "\n"


def load_answer_note(repo_root: Path, domain: str) -> str | None:
    """ドメインが回答に必ず添える注記（``domain.yaml`` の ``answer_note``）。無ければ None。

    例：住宅ローンのパックの「計算例であり、金融上の助言ではありません」。プロンプトでの
    お願いではなく、検証に通った回答の末尾に Agent が決定的に付ける。数字を含めない
    （検証の後に付けるため。``domain.yaml`` のスキーマで検査する）。
    """
    import yaml

    manifest_path = repo_root / "domains" / domain / "domain.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    note = str(manifest.get("answer_note") or "").strip()
    return note or None


def rejection_feedback(problems: Sequence[str]) -> str:
    """差し戻しの指摘（LLM への利用者メッセージ）。"""
    lines = "\n".join(f"- {p}" for p in problems)
    return (
        "検証器が回答テンプレートを差し戻しました。次の点を直したテンプレートを出し直してください。\n"
        f"{lines}\n"
        "数値はツール結果の出典 ID のプレースホルダ（[[出典ID]]・[[出典ID|書式]]）でだけ引用し、"
        "数字を直接書かないでください（利用者が質問に書いた数値の引用を除く）。"
        "必要な値が無ければ、ツールで計算してから引用してください。"
    )


class Agent:
    """1 つのゲートウェイと LLM で、質問に答える。"""

    def __init__(
        self,
        *,
        gateway: GatewayLike,
        llm: LLM,
        system_prompt: str,
        verifier: Verifier | None = None,
        trace_dir: Path | str = DEFAULT_TRACE_DIR,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        domain: str | None = None,
        answer_note: str | None = None,
    ) -> None:
        """
        :param answer_note: 検証に通った回答の末尾に必ず付ける注記（:func:`load_answer_note`）。
        """
        if verifier is None:
            from core.verifier import verify

            verifier = verify
        self.gateway = gateway
        self.llm = llm
        self.system_prompt = system_prompt
        self.verifier = verifier
        self.trace_dir = Path(trace_dir)
        self.max_tool_rounds = max_tool_rounds
        self.max_retries = max_retries
        self.domain = domain
        self.answer_note = answer_note

    async def ask(self, question: str, *, run_id: str | None = None) -> AgentResult:
        return await _Run(self, question, TraceWriter(self.trace_dir, run_id)).execute()


class _Run:
    """1 回の質問の状態（履歴・費用・回数）。"""

    def __init__(self, agent: Agent, question: str, trace: TraceWriter) -> None:
        self.agent = agent
        self.gw = agent.gateway
        self.question = question
        self.trace = trace
        self.tools = sorted(self.gw.tool_specs(), key=lambda t: t.name)
        # 履歴は追記のみ（応答の内容は加工せずに戻す）
        self.messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        self.cost = Decimal(0)
        self.llm_calls = 0
        self.tool_calls = 0
        self.tool_rounds = 0
        self.drafts = 0
        self.rejected = 0
        self.verdict: Verdict | None = None
        self.template: str | None = None

    async def execute(self) -> AgentResult:
        self.trace.emit(
            "question",
            question=self.question,
            domain=self.agent.domain,
            llm=type(self.agent.llm).__name__,
            model=self.agent.llm.model,
            tools=[t.name for t in self.tools],
        )
        while True:
            try:
                turn = await self._call_llm()
            except BudgetExceeded as e:
                self.trace.emit("budget_exceeded", reason=str(e))
                return self._finish("budget_exceeded", budget_answer(e))
            except LLMError as e:
                self.trace.emit("llm_error", kind=e.kind, error=str(e))
                answer = LLM_ERROR_ANSWERS.get(e.kind, LLM_ERROR_ANSWER)
                return self._finish("llm_error", answer)

            if turn.stop_reason == "refusal":
                # 拒否された応答（部分的なツール呼び出しを含みうる）は実行しない
                return self._finish("refusal", REFUSAL_ANSWER)
            if turn.stop_reason == "max_tokens":
                # 切れたツール入力は実行しない
                return self._finish("max_tokens", TRUNCATED_ANSWER)

            if turn.tool_uses:
                if self.tool_rounds >= self.agent.max_tool_rounds:
                    return self._finish("tool_round_limit", TOOL_LIMIT_ANSWER)
                self.tool_rounds += 1
                await self._run_tools(turn.tool_uses)
                continue

            result = self._review(turn.text)
            if result is not None:
                return result

    async def _call_llm(self) -> LLMTurn:
        self.gw.budget.check()  # 上限に達していれば BudgetExceeded（LLM は呼ばない）
        turn = await self.agent.llm.complete(
            system=self.agent.system_prompt, messages=self.messages, tools=self.tools
        )
        self.llm_calls += 1
        usd = Decimal(0)
        for charge in turn.charges:
            usd += Decimal(self.gw.budget.record(charge.model, dict(charge.usage)))
        self.cost += usd
        self.trace.emit(
            "llm_call",
            model=turn.model,
            stop_reason=turn.stop_reason,
            stop_details=turn.stop_details,
            usage=turn.usage,
            charges=turn.charges,
            usd=usd,
            text=turn.text,
            tool_uses=turn.tool_uses,
        )
        self.messages.append({"role": "assistant", "content": turn.raw_content})
        return turn

    async def _run_tools(self, uses: Sequence[ToolUse]) -> None:
        for use in uses:
            self.trace.emit("tool_call", tool_use_id=use.id, name=use.name, input=use.input)
        outcomes = await asyncio.gather(*(self.gw.call(u.name, u.input) for u in uses))
        self.tool_calls += len(uses)
        results: list[dict[str, Any]] = []
        for use, outcome in zip(uses, outcomes, strict=True):
            self.trace.emit("tool_result", tool_use_id=use.id, outcome=outcome)
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": use.id,
                "content": json.dumps(outcome.for_llm(), ensure_ascii=False),
            }
            if outcome.error is not None:
                block["is_error"] = True
            results.append(block)
        # 並列の呼び出しの結果は 1 つの利用者メッセージにまとめて返す
        self.messages.append({"role": "user", "content": results})

    def _review(self, template: str) -> AgentResult | None:
        """下書きを検証する。合格なら結果、差し戻すなら None（履歴に指摘を追記）。"""
        self.drafts += 1
        self.template = template
        if template.strip():
            verdict = self.agent.verifier(template, self.question, self.gw.sources)
        else:
            verdict = Verdict(ok=False, problems=("回答の本文が空です。",))
        self.verdict = verdict
        self.trace.emit(
            "verdict",
            draft=self.drafts,
            template=template,
            ok=verdict.ok,
            problems=verdict.problems,
            cited=verdict.cited,
        )
        if verdict.ok:
            answer = verdict.rendered or ""
            if self.agent.answer_note:
                answer += "\n\n" + self.agent.answer_note
            return self._finish("answered", answer)
        self.rejected += 1
        if self.rejected > self.agent.max_retries:
            return self._finish("fallback", FALLBACK_ANSWER)
        self.messages.append({"role": "user", "content": rejection_feedback(verdict.problems)})
        return None

    def _finish(self, status: str, answer: str) -> AgentResult:
        cited: tuple[SourceValue, ...] = ()
        if status == "answered" and self.verdict is not None:
            sources = self.gw.sources
            cited = tuple(sources[s] for s in self.verdict.cited if s in sources)
        self.trace.emit(
            "answer",
            status=status,
            answer=answer,
            cited=[s.source_id for s in cited],
            cost_usd=self.cost,
            drafts=self.drafts,
            drafts_rejected=self.rejected,
            llm_calls=self.llm_calls,
            tool_calls=self.tool_calls,
        )
        return AgentResult(
            answer=answer,
            status=status,
            run_id=self.trace.run_id,
            trace_path=self.trace.path,
            verdict=self.verdict,
            cited=cited,
            cost_usd=self.cost,
            drafts=self.drafts,
            drafts_rejected=self.rejected,
            llm_calls=self.llm_calls,
            tool_calls=self.tool_calls,
            template=self.template,
            problems=self.verdict.problems if self.verdict and not self.verdict.ok else (),
        )
