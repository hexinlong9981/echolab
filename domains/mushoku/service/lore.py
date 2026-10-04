"""無職転生の設定の検索・時系列・旅程。ネタバレ防止の絞り込みはここで必ず行う（ADR-0012）。

- 進み具合（``progress``）は利用者が指定する（``novel:5`` = 小説 5 巻まで、
  ``anime:2-12`` = アニメ 2 期 12 話まで）。LLM には見せず、ゲートウェイが入力に加える
  （``domain.yaml`` の ``user_context``）。
- 申告した媒体の列だけで絞り込み、媒体の間で換算しない。
  その媒体の注記が無い項目は返さない（既定拒否）。
- 見えない項目は「存在しない」と同じに扱う（誤りの文面も同じにして、存在を漏らさない）。
- 事実の文は数字を含まない。数値（年・年齢・日数・巻・話）は ``values`` で返す（ADR-0001）。
"""

from __future__ import annotations

import heapq
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "draft-1"
MAX_NOVEL_VOL = 26
NOT_FOUND = "見つかりません（まだ読んでいない範囲か、資料にありません）"


class LoreInputError(ValueError):
    """入力が不正、または該当が無い。メッセージはそのまま LLM と利用者に見せる。"""


# ---------------------------------------------------------------------------
# 進み具合
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Progress:
    """利用者の進み具合。``medium`` は ``novel`` か ``anime``、``position`` は比べられる組。"""

    medium: str
    position: tuple[int, ...]

    def allows(self, item: Mapping[str, Any]) -> bool:
        """その項目が見えるか。申告した媒体の注記だけを見る（無ければ見せない）。"""
        if self.medium == "novel":
            vol = item.get("novel_vol")
            return isinstance(vol, int) and (vol,) <= self.position
        ep = item.get("anime_ep")
        return isinstance(ep, str) and _anime(ep) <= self.position


def parse_progress(text: Any) -> Progress:
    if not isinstance(text, str):
        raise LoreInputError(
            "progress がありません（利用者が --context progress=novel:5 などで指定します）"
        )
    m = re.fullmatch(r"(novel|anime):(.+)", text.strip())
    if m is None:
        raise LoreInputError(f"progress の形式が不正です: {text}（novel:<巻> か anime:<期>-<話>）")
    medium, rest = m.groups()
    if medium == "novel":
        if not rest.isdigit() or not 1 <= int(rest) <= MAX_NOVEL_VOL:
            raise LoreInputError(f"小説の巻は 1〜{MAX_NOVEL_VOL} です: {rest}")
        return Progress("novel", (int(rest),))
    try:
        return Progress("anime", _anime(rest))
    except ValueError as e:
        raise LoreInputError(f"アニメの進み具合は <期>-<話> です（例 anime:2-12）: {rest}") from e


def _anime(ep: str) -> tuple[int, int]:
    m = re.fullmatch(r"([1-9])-([0-9]{1,2})", ep)
    if m is None:
        raise ValueError(ep)
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------------------
# データ
# ---------------------------------------------------------------------------


@cache
def _load(name: str) -> dict[str, Any]:
    return yaml.safe_load((DATA_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lower()


def _names(item: Mapping[str, Any], progress: Progress | None = None) -> list[str]:
    """名前・別名・ID。正体のネタバレになる別名（secret_aliases）は、明かされた後だけ含める。"""
    names = [item["id"], item["name"], *item.get("aliases", [])]
    if progress is not None:
        names += [a["name"] for a in item.get("secret_aliases", []) if progress.allows(a)]
    return names


def _resolve(
    items: Iterable[Mapping[str, Any]], name: str, progress: Progress
) -> Mapping[str, Any]:
    """名前・別名・ID から、見えている項目を探す。見えない・無いは同じ誤り。"""
    key = _norm(name)
    for item in items:
        if progress.allows(item) and any(_norm(n) == key for n in _names(item, progress)):
            return item
    raise LoreInputError(f"{name}: {NOT_FOUND}")


def _cite(prefix: str, item: Mapping[str, Any], progress: Progress) -> dict[str, Decimal]:
    """出典の巻・話（申告した媒体の分だけ）。"""
    if progress.medium == "novel":
        return {f"{prefix}_novel_vol": Decimal(item["novel_vol"])}
    season, episode = _anime(item["anime_ep"])
    return {f"{prefix}_anime_season": Decimal(season), f"{prefix}_anime_episode": Decimal(episode)}


@dataclass(frozen=True)
class Result:
    values: dict[str, Decimal]
    texts: dict[str, str]
    unverified: tuple[str, ...]


# ---------------------------------------------------------------------------
# ツール
# ---------------------------------------------------------------------------


def search(i: Mapping[str, Any]) -> Result:
    """キーワード（すべて含む）で事実を探す。人物・場所はタグの名前・別名でも当たる。"""
    progress = parse_progress(i.get("progress"))
    keywords = i.get("keywords")
    if (
        not isinstance(keywords, list)
        or not keywords
        or not all(isinstance(k, str) and k.strip() for k in keywords)
    ):
        raise LoreInputError("keywords は 1 つ以上の文字列の配列です")
    limit = i.get("limit", 5)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise LoreInputError("limit は 1〜10 の整数です")
    tag_names = {
        item["id"]: _names(item, progress)
        for item in [*_load("people")["people"], *_load("places")["places"]]
        if progress.allows(item)  # 見えない人物・場所の別名では当てない
    }
    hits = []
    for fact in _load("facts")["facts"]:
        if not progress.allows(fact):
            continue
        haystack = _norm(
            " ".join(
                [
                    fact["text"],
                    *fact["tags"],
                    *(n for t in fact["tags"] for n in tag_names.get(t, [])),
                ]
            )
        )
        if all(_norm(k) in haystack for k in keywords):
            hits.append(fact)
    hits = hits[:limit]
    values: dict[str, Decimal] = {"count": Decimal(len(hits))}
    for fact in hits:
        values.update(_cite(fact["id"], fact, progress))
    return Result(
        values, {f["id"]: f["text"] for f in hits}, tuple(f"facts:{f['id']}" for f in hits)
    )


def age(i: Mapping[str, Any]) -> Result:
    """出来事の年の、その人物の年齢（出来事の年 − 生年）。"""
    progress = parse_progress(i.get("progress"))
    person = _resolve(_load("people")["people"], _text(i, "person"), progress)
    event = _resolve(_load("events")["events"], _text(i, "event"), progress)
    if "birth_year" not in person:
        raise LoreInputError(f"{person['name']} の生年は資料にありません")
    years = event["year"] - person["birth_year"]
    return Result(
        {
            "age": Decimal(years),
            "birth_year": Decimal(person["birth_year"]),
            "event_year": Decimal(event["year"]),
        },
        {},
        (f"people:{person['id']}", f"events:{event['id']}"),
    )


def span(i: Mapping[str, Any]) -> Result:
    """2 つの出来事の間の年数（後 − 前。逆順なら負）。"""
    progress = parse_progress(i.get("progress"))
    events = _load("events")["events"]
    a = _resolve(events, _text(i, "from_event"), progress)
    b = _resolve(events, _text(i, "to_event"), progress)
    return Result(
        {
            "years": Decimal(b["year"] - a["year"]),
            "from_year": Decimal(a["year"]),
            "to_year": Decimal(b["year"]),
        },
        {},
        (f"events:{a['id']}", f"events:{b['id']}"),
    )


def route(i: Mapping[str, Any]) -> Result:
    """自作の地図で、見えている道だけを使った最短の旅程（日数の合計）。"""
    progress = parse_progress(i.get("progress"))
    data = _load("places")
    places = [p for p in data["places"] if progress.allows(p)]
    start = _resolve(places, _text(i, "from"), progress)
    goal = _resolve(places, _text(i, "to"), progress)
    visible = {p["id"] for p in places}
    graph: dict[str, list[tuple[str, int, Mapping[str, Any]]]] = {}
    for r in data["routes"]:
        if progress.allows(r) and r["from"] in visible and r["to"] in visible:
            graph.setdefault(r["from"], []).append((r["to"], r["days"], r))
            graph.setdefault(r["to"], []).append((r["from"], r["days"], r))
    path = _dijkstra(graph, start["id"], goal["id"])
    if path is None:
        raise LoreInputError(
            f"{start['name']} から {goal['name']} への道が見つかりません"
            "（まだ読んでいない範囲の道は使いません）"
        )
    names = {p["id"]: p["name"] for p in places}
    total = sum(days for _, days, _ in path)
    return Result(
        {"total_days": Decimal(total), "legs": Decimal(len(path))},
        {"path": " → ".join([names[start["id"]], *(names[node] for node, _, _ in path)])},
        tuple(dict.fromkeys(f"places:{p}" for p in [start["id"], *(n for n, _, _ in path)])),
    )


def _dijkstra(
    graph: Mapping[str, Sequence[tuple[str, int, Any]]], start: str, goal: str
) -> list[tuple[str, int, Any]] | None:
    """最短経路（区間の列）。同じ距離なら ID の順で決まる（結果を決定的にする）。"""
    queue: list[tuple[int, str]] = [(0, start)]
    best = {start: 0}
    prev: dict[str, tuple[str, int, Any]] = {}
    while queue:
        dist, node = heapq.heappop(queue)
        if node == goal:
            legs = []
            while node != start:
                before, days, edge = prev[node]
                legs.append((node, days, edge))
                node = before
            return list(reversed(legs))
        if dist > best.get(node, dist):
            continue
        for nxt, days, edge in sorted(graph.get(node, []), key=lambda e: e[0]):
            nd = dist + days
            if nd < best.get(nxt, nd + 1):
                best[nxt] = nd
                prev[nxt] = (node, days, edge)
                heapq.heappush(queue, (nd, nxt))
    return [] if start == goal else None


def _text(i: Mapping[str, Any], key: str) -> str:
    value = i.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LoreInputError(f"{key} は空でない文字列です")
    return value


#: ツール名 → 処理。MCP サーバと試験が共用する。
TOOLS = {
    "lore.search": search,
    "timeline.age": age,
    "timeline.span": span,
    "map.route": route,
}
