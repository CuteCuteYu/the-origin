"""NPC 社会关系网辅助：读取 ``scenario.json`` 编译进 ``world.json`` 的
``social_network`` 区块。

设计目标：
- 用结构化数据描述 NPC 之间的关系、彼此看法、合作经历与共同社交事件；
- 人类 NPC 提示词只注入「与当前 NPC 有关」的视角，不泄露对方的私下看法；
- AI 玩家只拿到 ``visibility=public`` 的关系/事件摘要，保持信息不对称；
- 配置缺失或字段不完整时安静降级，不影响旧场景。

数据结构（全部可选）::

    {
      "cast": {"npc_01": "陈静（行政前台）", "npc_02": "周明远（资深工程师）"},
      "relations": [
        {
          "from": "npc_01",
          "to": "npc_02",
          "relation": "老同事 / 互相帮忙",
          "from_view": "陈静对周明远的私下看法",
          "to_view": "周明远对陈静的私下看法",
          "opinion": "双方都认可的公开评价（可选，作为视角缺失时的兜底）",
          "collaboration_history": ["一起做过白鹭项目"],
          "social_events": [
            {"date": "2026-09-19", "title": "团建剧本杀", "summary": "两人因排期争执"}
          ],
          "tension": "排期 vs 质量",
          "trust": 70,
          "visibility": "public | team | private"
        }
      ],
      "events": [
        {
          "event_id": "evt_20260919_scriptkill",
          "date": "2026-09-19",
          "title": "团建剧本杀",
          "participants": ["npc_01", "npc_02", "npc_03"],
          "summary": "周明远和方雨桐因排期当场争执。",
          "impact": {"npc_01": "陈静记得的细节", "npc_02": "周明远记得的细节"},
          "visibility": "public"
        }
      ]
    }
"""

from __future__ import annotations

from typing import Any

VISIBILITIES = ("public", "team", "private")


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def actor_name(network: dict, actor_id: str) -> str:
    """优先用 cast 里的显示名，缺失时回退到 ID。"""
    cast = _dict(network.get("cast"))
    name = _text(cast.get(actor_id))
    return name or _text(actor_id)


def event_line(item: Any) -> str:
    """把一条 social_events 条目渲染成单行文本。"""
    if isinstance(item, dict):
        date = _text(item.get("date"))
        title = _text(item.get("title"))
        summary = _text(item.get("summary"))
        prefix = f"{date} " if date else ""
        if title and summary:
            return f"{prefix}{title}：{summary}"
        return f"{prefix}{title or summary}".strip()
    return _text(item)


def _history(value: Any) -> list[str]:
    out: list[str] = []
    for item in _list(value):
        text = _text(item)
        if text:
            out.append(text)
    return out


def _trust(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if 0 <= value <= 100:
        return value
    return None


def _visibility(value: Any) -> str:
    text = _text(value).lower()
    return text if text in VISIBILITIES else "team"


def relation_entries(network: dict, npc_id: str) -> list[dict]:
    """返回与 ``npc_id`` 有关的边。

    每条边的 ``view`` 只包含当前 NPC 自己的视角：
    - 当前 NPC 是 ``from`` → 取 ``from_view``；
    - 当前 NPC 是 ``to`` → 取 ``to_view``；
    - 都缺失时用双方共识的 ``opinion`` 兜底。
    对方的私下看法永远不会出现在返回值里。
    """
    entries: list[dict] = []
    npc_id = _text(npc_id)
    if not npc_id:
        return entries
    for rel in _list(network.get("relations")):
        if not isinstance(rel, dict):
            continue
        a = _text(rel.get("from"))
        b = _text(rel.get("to"))
        if not a or not b or a == b:
            continue
        if a == npc_id:
            direction, other_id = "out", b
            view = _text(rel.get("from_view")) or _text(rel.get("opinion"))
        elif b == npc_id:
            direction, other_id = "in", a
            view = _text(rel.get("to_view")) or _text(rel.get("opinion"))
        else:
            continue

        entries.append(
            {
                "direction": direction,
                "other_id": other_id,
                "other_name": actor_name(network, other_id),
                "relation": _text(rel.get("relation")),
                "view": view,
                "collaboration_history": _history(rel.get("collaboration_history")),
                "social_events": [
                    line
                    for line in (event_line(x) for x in _list(rel.get("social_events")))
                    if line
                ],
                "tension": _text(rel.get("tension")),
                "trust": _trust(rel.get("trust")),
                "visibility": _visibility(rel.get("visibility")),
            }
        )
    return entries


def event_entries(network: dict, npc_id: str) -> list[dict]:
    """返回当前 NPC 参与过的共同事件，只保留该 NPC 自己的 impact。"""
    entries: list[dict] = []
    npc_id = _text(npc_id)
    if not npc_id:
        return entries
    for event in _list(network.get("events")):
        if not isinstance(event, dict):
            continue
        participants = [
            pid for pid in (_text(x) for x in _list(event.get("participants"))) if pid
        ]
        if npc_id not in participants:
            continue
        impact_map = _dict(event.get("impact"))
        entries.append(
            {
                "event_id": _text(event.get("event_id")),
                "date": _text(event.get("date")),
                "title": _text(event.get("title")),
                "summary": _text(event.get("summary")),
                "participants": [actor_name(network, pid) for pid in participants],
                "impact": _text(impact_map.get(npc_id)),
                "visibility": _visibility(event.get("visibility")),
            }
        )
    return entries


def public_graph(network: dict, playable_ids: list[str]) -> list[dict]:
    """AI 玩家可见的公开关系/事件摘要。

    只返回 ``visibility=public`` 且双方都是可对话 NPC 的边/事件，
    不包含任何 ``from_view`` / ``to_view`` 私下看法。
    """
    ids = {_text(x) for x in playable_ids if _text(x)}
    graph: list[dict] = []
    if not ids:
        return graph

    for rel in _list(network.get("relations")):
        if not isinstance(rel, dict):
            continue
        a = _text(rel.get("from"))
        b = _text(rel.get("to"))
        if a not in ids or b not in ids or a == b:
            continue
        if _visibility(rel.get("visibility")) != "public":
            continue
        note_parts = [
            text.rstrip("。；;，, ")
            for text in _history(rel.get("collaboration_history"))
        ]
        tension = _text(rel.get("tension")).rstrip("。；;，, ")
        if tension:
            note_parts.append(f"张力：{tension}")
        graph.append(
            {
                "kind": "relation",
                "a": actor_name(network, a),
                "b": actor_name(network, b),
                "relation": _text(rel.get("relation")),
                "note": "；".join(note_parts),
            }
        )

    for event in _list(network.get("events")):
        if not isinstance(event, dict):
            continue
        participants = [
            pid for pid in (_text(x) for x in _list(event.get("participants"))) if pid
        ]
        if len(ids.intersection(participants)) < 2:
            continue
        if _visibility(event.get("visibility")) != "public":
            continue
        graph.append(
            {
                "kind": "event",
                "date": _text(event.get("date")),
                "title": _text(event.get("title")),
                "summary": _text(event.get("summary")),
                "participants": [actor_name(network, pid) for pid in participants],
            }
        )
    return graph
