"""比較ツール：差・比・増加率（ADR-0005）。

LLM に四則演算をさせないため、派生値はここで決定的に計算する。ドメインに依存しない。
LLM から見た入力は数値ではなく出典 ID（``{"a": "c1.total", "b": "c2.total"}``）で、
出典 ID から値への解決はゲートウェイが行う。ここには数値どうしの純粋な計算だけを置く。
"""

from core.compare.compare import (
    COMPARE_SPECS,
    COMPARE_TOOLS,
    diff,
    ratio,
)

__all__ = ["COMPARE_SPECS", "COMPARE_TOOLS", "diff", "ratio"]
