"""social_network：视角隔离、事件 impact、AI 公开关系图过滤。"""

import json

import social

NETWORK = {
    "cast": {
        "npc_01": "陈静（行政前台）",
        "npc_02": "周明远（资深工程师）",
        "npc_03": "方雨桐（产品总监）",
        "ceo": "许沉舟（CEO）",
    },
    "relations": [
        {
            "from": "npc_01",
            "to": "npc_02",
            "relation": "老同事 / 互相帮忙",
            "from_view": "陈静私下觉得老周靠谱",
            "to_view": "周明远私下觉得小陈嘴快",
            "collaboration_history": ["一起收快递"],
            "social_events": [
                {"date": "2026-09-19", "title": "团建", "summary": "一起被罚酒"}
            ],
            "tension": "无",
            "trust": 75,
            "visibility": "team",
        },
        {
            "from": "npc_02",
            "to": "npc_03",
            "relation": "公开冲突",
            "from_view": "周明远私下觉得方总太急",
            "to_view": "方雨桐私下觉得老周太慢",
            "collaboration_history": ["白鹭项目"],
            "tension": "排期 vs 质量",
            "trust": 45,
            "visibility": "public",
        },
        {
            "from": "npc_01",
            "to": "npc_03",
            "relation": "私下抱怨",
            "from_view": "陈静私下有点怕方总",
            "to_view": "方雨桐觉得小陈懂事",
            "visibility": "private",
        },
        {
            "from": "npc_01",
            "to": "ceo",
            "relation": "上下级",
            "from_view": "陈静不敢多说话",
            "visibility": "team",
        },
    ],
    "events": [
        {
            "event_id": "evt_1",
            "date": "2026-09-19",
            "title": "团建剧本杀",
            "participants": ["npc_01", "npc_02", "npc_03"],
            "summary": "周明远和方雨桐争执。",
            "impact": {
                "npc_01": "陈静记得气氛很僵",
                "npc_02": "周明远记得方总拍桌子",
                "npc_03": "方雨桐记得老周顶嘴",
            },
            "visibility": "public",
        }
    ],
}


def test_relation_entries_only_expose_own_view():
    n1 = social.relation_entries(NETWORK, "npc_01")
    rel1 = next(item for item in n1 if item["other_id"] == "npc_02")
    assert rel1["view"] == "陈静私下觉得老周靠谱"
    assert "周明远私下觉得小陈嘴快" not in rel1["view"]
    assert rel1["collaboration_history"] == ["一起收快递"]
    assert rel1["social_events"] == ["2026-09-19 团建：一起被罚酒"]
    assert rel1["trust"] == 75

    n2 = social.relation_entries(NETWORK, "npc_02")
    rel2 = next(item for item in n2 if item["other_id"] == "npc_01")
    assert rel2["view"] == "周明远私下觉得小陈嘴快"
    assert "陈静私下觉得老周靠谱" not in rel2["view"]


def test_event_entries_only_expose_own_impact():
    events = social.event_entries(NETWORK, "npc_01")
    assert len(events) == 1
    event = events[0]
    assert event["title"] == "团建剧本杀"
    assert event["impact"] == "陈静记得气氛很僵"
    assert "周明远记得方总拍桌子" not in json.dumps(event, ensure_ascii=False)
    assert event["participants"] == [
        "陈静（行政前台）",
        "周明远（资深工程师）",
        "方雨桐（产品总监）",
    ]


def test_public_graph_filters_private_and_non_playable_edges():
    graph = social.public_graph(NETWORK, ["npc_01", "npc_02", "npc_03"])
    text = json.dumps(graph, ensure_ascii=False)

    assert any(item["kind"] == "relation" and item["relation"] == "公开冲突" for item in graph)
    assert any(item["kind"] == "event" and item["title"] == "团建剧本杀" for item in graph)
    # team / private 关系不进入 AI 玩家简报
    assert "老同事 / 互相帮忙" not in text
    assert "私下抱怨" not in text
    assert "上下级" not in text
    # 任何私下看法都不应泄露
    assert "私下" not in text


def test_actor_name_falls_back_to_id():
    assert social.actor_name(NETWORK, "npc_01") == "陈静（行政前台）"
    assert social.actor_name(NETWORK, "unknown") == "unknown"
