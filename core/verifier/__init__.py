"""数値トレース検証器とレンダラ（ADR-0005・ADR-0008）。

LLM の最終回答はテンプレートで、数値はプレースホルダ ``[[c1.total]]`` で引用する。
検証器はテンプレートを検査し、レンダラはプレースホルダを決定的に数値へ置き換える。
"""

from core.verifier.render import format_value, render
from core.verifier.verify import verify

__all__ = ["format_value", "render", "verify"]
