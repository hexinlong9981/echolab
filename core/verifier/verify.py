"""回答テンプレートの検証（ADR-0005・ADR-0008）。

検査する内容:

1. プレースホルダの形式が正しく、出典 ID がこの質問の中で発行されたものであること。
2. プレースホルダを除いた本文（NFKC で正規化）に現れる数字が、次のどれかに当たること。

   - 利用者の質問にある数値の引用（桁区切りは無視し、``x%`` と ``x/100`` は同じとみなす）
   - 許可リスト：行頭の箇条書きの番号（``1.``・``2)``・``３．``）、
     10 以下の整数の直後に助数詞が続くもの。日本語の「つ・点・種類・位・番目」と、
     中国語で答えた場合の「个・种・项・条・步」、英語で答えた場合の「ways・points・steps」などの名詞
     （回答は利用者の言語で書くため）。
     このリポジトリの文書の書き方「3 つの方法」に合わせ、間の空白 1 つは許す

符号は数値の一部とみなさない（``-5`` の ``5`` を照合する）。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal

from core.contracts import PLACEHOLDER, UNVERIFIED_NOTE, SourceValue, Verdict
from core.verifier.render import BRACKETS, render

#: 本文中の数値。桁区切りは 3 桁ずつのものだけを 1 つの数とみなす。
NUMBER = re.compile(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?%?")

#: 行頭の箇条書きの番号（NFKC 後）。``1.5`` のような小数は除く。
LIST_MARKER = re.compile(r"^([ \t]*)\(?\d{1,3}[.)](?!\d)", re.MULTILINE)

#: 数値でない語として許す助数詞。
COUNTER_SUFFIXES = ("つ", "点", "種類", "位", "番目", "个", "种", "项", "条", "步")
COUNTER_MAX = 10

#: 英語で答えた場合の、数値でない語として許す名詞（「2 ways」「3 steps」など）。
EN_COUNTER = re.compile(
    r"(?:ways?|points?|steps?|options?|items?|reasons?|types?|kinds?|parts?|things?|tools?|builds?)\b",
    re.IGNORECASE,
)


def _values(token: str) -> set[Decimal]:
    """数値の表記から、等しいとみなす値の集合を作る（``60%`` → {60, 0.6}）。"""
    percent = token.endswith("%")
    v = Decimal(token.rstrip("%").replace(",", ""))
    return {v, v / 100} if percent else {v}


def _is_counter(token: str, following: str) -> bool:
    if not (token.isdigit() and int(token) <= COUNTER_MAX):
        return False
    if following[:1] in (" ", "\t"):
        following = following[1:]
    return following.startswith(COUNTER_SUFFIXES) or bool(EN_COUNTER.match(following))


def verify(template: str, question: str, sources: Mapping[str, SourceValue]) -> Verdict:
    """回答テンプレートを検査し、通れば数値に置き換えた回答を返す。"""
    problems: list[str] = []
    cited: list[str] = []
    for m in BRACKETS.finditer(template):
        p = PLACEHOLDER.fullmatch(m.group(0))
        if p is None:
            problems.append(
                f"プレースホルダ「{m.group(0)}」の形式が不正です。"
                "[[c1.total]]・[[c1.total|0]]・[[c1.ratio|%1]] の形で書いてください。"
            )
            continue
        source_id = p.group("source")
        if source_id not in sources:
            problems.append(
                f"出典 ID「{source_id}」はこの質問のツール結果にありません。"
                "ツールが返した出典 ID だけを引用してください。"
            )
        elif source_id not in cited:
            cited.append(source_id)

    # プレースホルダは数字を含むので、空白に置き換えてから本文の数字を探す
    body = unicodedata.normalize("NFKC", BRACKETS.sub(" ", template))
    body = LIST_MARKER.sub(r"\1 ", body)
    allowed: set[Decimal] = set()
    for m in NUMBER.finditer(unicodedata.normalize("NFKC", question)):
        allowed |= _values(m.group(0))
    for m in NUMBER.finditer(body):
        token = m.group(0)
        if _is_counter(token, body[m.end() :]):
            continue
        if _values(token) & allowed:
            continue
        problems.append(
            f"数値「{token}」の出典がありません。ツールの結果は [[出典ID]] で引用し、"
            "差や比は比較ツールで計算してください（質問にある数値の引用は可）。"
        )

    if problems:
        return Verdict(ok=False, problems=tuple(problems), cited=tuple(cited))
    rendered = render(template, sources)
    if any(sources[s].unverified_inputs for s in cited):
        rendered += "\n\n" + UNVERIFIED_NOTE
    return Verdict(ok=True, rendered=rendered, cited=tuple(cited))
