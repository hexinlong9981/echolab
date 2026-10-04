"""LLM の抽象層と実装（Claude・Gemini・台本）。"""

from core.agent.llm.base import LLM, Charge, LLMError, LLMTurn, ToolUse, normalize_usage
from core.agent.llm.claude import AnthropicLLM
from core.agent.llm.gemini import GeminiLLM
from core.agent.llm.scripted import ScriptedLLM, ScriptExhausted, ScriptMismatch

__all__ = [
    "LLM",
    "AnthropicLLM",
    "Charge",
    "GeminiLLM",
    "LLMError",
    "LLMTurn",
    "ScriptExhausted",
    "ScriptMismatch",
    "ScriptedLLM",
    "ToolUse",
    "normalize_usage",
]
