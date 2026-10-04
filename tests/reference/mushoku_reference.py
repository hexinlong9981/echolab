"""無職転生のパック（domains/mushoku/service/lore.py）の参照実装。

パックとは別に書き、同じゴールデンケースと照合する（ADR-0012）。
- 旅程はダイクストラ法ではなく、見えている道だけで作った単純な経路をすべて調べて最短を選ぶ。
- ネタバレ防止の絞り込み（媒体ごと・注記の無いものは出さない・正体の別名は明かされた後だけ）も
  別に書き直す。入力の検査はしない（ゴールデンケースの入力は正しい前提）。
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parents[2] / "domains/mushoku/data/draft-1"


def _data(name: str) -> dict:
    return yaml.safe_load((DATA / f"{name}.yaml").read_text(encoding="utf-8"))


def _key(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).lower()


def _visible(item: dict, progress: str) -> bool:
    medium, _, value = progress.partition(":")
    if medium == "novel":
        return item.get("novel_vol") is not None and item["novel_vol"] <= int(value)
    if item.get("anime_ep") is None:
        return False
    season, episode = (int(x) for x in item["anime_ep"].split("-"))
    want_season, want_episode = (int(x) for x in value.split("-"))
    return season < want_season or (season == want_season and episode <= want_episode)


def _names(item: dict, progress: str) -> list[str]:
    secret = [a["name"] for a in item.get("secret_aliases", []) if _visible(a, progress)]
    return [item["id"], item["name"], *item.get("aliases", []), *secret]


def _find(items: list[dict], name: str, progress: str) -> dict:
    for item in items:
        if _visible(item, progress) and _key(name) in {_key(n) for n in _names(item, progress)}:
            return item
    raise ValueError(f"{name}: 見つかりません（まだ読んでいない範囲か、資料にありません）")


def _cite(fact: dict, progress: str) -> dict[str, float]:
    if progress.startswith("novel:"):
        return {f"{fact['id']}_novel_vol": float(fact["novel_vol"])}
    season, episode = fact["anime_ep"].split("-")
    return {
        f"{fact['id']}_anime_season": float(season),
        f"{fact['id']}_anime_episode": float(episode),
    }


def search(i: dict) -> tuple[dict[str, float], dict[str, str]]:
    progress = i["progress"]
    entities = {
        e["id"]: _names(e, progress)
        for e in _data("people")["people"] + _data("places")["places"]
        if _visible(e, progress)
    }
    found = []
    for fact in _data("facts")["facts"]:
        if not _visible(fact, progress):
            continue
        words = [fact["text"], *fact["tags"]]
        for tag in fact["tags"]:
            words += entities.get(tag, [])
        text = _key(" ".join(words))
        if all(_key(k) in text for k in i["keywords"]):
            found.append(fact)
    found = found[: i.get("limit", 5)]
    values = {"count": float(len(found))}
    for fact in found:
        values.update(_cite(fact, progress))
    return values, {f["id"]: f["text"] for f in found}


def age(i: dict) -> tuple[dict[str, float], dict[str, str]]:
    person = _find(_data("people")["people"], i["person"], i["progress"])
    event = _find(_data("events")["events"], i["event"], i["progress"])
    return {
        "age": float(event["year"] - person["birth_year"]),
        "birth_year": float(person["birth_year"]),
        "event_year": float(event["year"]),
    }, {}


def span(i: dict) -> tuple[dict[str, float], dict[str, str]]:
    events = _data("events")["events"]
    a = _find(events, i["from_event"], i["progress"])
    b = _find(events, i["to_event"], i["progress"])
    return {
        "years": float(b["year"] - a["year"]),
        "from_year": float(a["year"]),
        "to_year": float(b["year"]),
    }, {}


def route(i: dict) -> tuple[dict[str, float], dict[str, str]]:
    progress = i["progress"]
    data = _data("places")
    places = [p for p in data["places"] if _visible(p, progress)]
    start = _find(places, i["from"], progress)["id"]
    goal = _find(places, i["to"], progress)["id"]
    ids = {p["id"] for p in places}
    edges = [
        r for r in data["routes"] if _visible(r, progress) and r["from"] in ids and r["to"] in ids
    ]

    best: tuple[float, list[str]] | None = None

    def walk(node: str, seen: list[str], days: float) -> None:
        nonlocal best
        if node == goal:
            if best is None or days < best[0]:
                best = (days, seen)
            return
        for r in edges:
            for a, b in ((r["from"], r["to"]), (r["to"], r["from"])):
                if a == node and b not in seen:
                    walk(b, [*seen, b], days + r["days"])

    walk(start, [start], 0.0)
    if best is None:
        raise ValueError("道が見つかりません")
    names = {p["id"]: p["name"] for p in places}
    return {"total_days": best[0], "legs": float(len(best[1]) - 1)}, {
        "path": " → ".join(names[n] for n in best[1])
    }


TOOLS = {"lore.search": search, "timeline.age": age, "timeline.span": span, "map.route": route}
