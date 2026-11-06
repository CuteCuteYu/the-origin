"""prompt_builder：14 层系统提示词的组装、世界真相遮蔽、记忆裁剪。"""

import gamestate
import prompt_builder as pb
import storage


def _ctx(npc_id):
    npc = storage.load_npc(npc_id)
    return {
        "clock": "16:35",
        "state": gamestate.load_state(npc_id, npc),
        "gossip": [{"npc_id": "npc_02", "from": "周明远", "text": "访客问过白板的事"}],
        "claims": [{"text": "访客自称睿析咨询", "npc_id": "npc_02", "heard_by": "周明远"}],
        "summary": "访客此前和陈静聊过咖啡机的事。",
    }


def test_system_prompt_contains_runtime_layers():
    world = storage.load_world()
    npc = storage.load_npc("npc_01")
    prompt = pb.build_system_prompt(world, npc, _ctx("npc_01"))

    assert "16:35" in prompt                      # 场景时钟层
    assert "访客问过白板的事" in prompt              # 同事八卦层
    assert "访客自称睿析咨询" in prompt              # 访客口径层
    assert "访客此前和陈静聊过咖啡机的事" in prompt    # 前情摘要层
    assert "心理状态" in prompt                     # 状态分档层
    assert "<state>" in prompt                     # 输出协议层


def test_world_truth_masked_for_regular_npcs():
    """普通员工只见过脱敏的「49x」，绝不能看到真实报价 499。"""
    world = storage.load_world()
    for npc_id in ("npc_01", "npc_02"):
        prompt = pb.build_system_prompt(world, storage.load_npc(npc_id), _ctx(npc_id))
        assert "499" not in prompt, f"{npc_id} 的提示词泄露了世界真相"
        assert "49x" in prompt


def test_build_messages_trims_by_summary_index():
    world = storage.load_world()
    npc = storage.load_npc("npc_01")
    history = []
    for i in range(10):
        role = "user" if i % 2 == 0 else "assistant"
        history.append({"role": role, "content": f"m{i}", "ts": "2026-10-16T16:00:00"})

    ctx = dict(_ctx("npc_01"), summarized_up_to=4)
    msgs = pb.build_messages(world, npc, history, "最新一问", ctx=ctx)

    assert msgs[0]["role"] == "system"
    assert msgs[-1] == {"role": "user", "content": "最新一问"}
    contents = [m["content"] for m in msgs]
    assert "m0" not in contents and "m3" not in contents   # 已压缩进摘要
    assert "m4" in contents                                # 摘要之后保留原文
    # 发给模型的消息只带 role/content
    assert all(set(m.keys()) == {"role", "content"} for m in msgs[1:])


def test_build_summary_messages_include_existing_and_batch():
    batch = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    msgs = pb.build_summary_messages("旧摘要内容", batch)
    assert msgs[0]["role"] == "system"
    assert "旧摘要内容" in msgs[1]["content"]
    assert "u1" in msgs[1]["content"] and "a1" in msgs[1]["content"]


def _world_with_social_network():
    world = dict(storage.load_world())
    world["social_network"] = {
        "cast": {
            "npc_01": "陈静（行政前台）",
            "npc_02": "周明远（资深工程师）",
        },
        "relations": [
            {
                "from": "npc_01",
                "to": "npc_02",
                "relation": "测试关系",
                "from_view": "结构化独有看法-陈静",
                "to_view": "结构化独有看法-周明远",
                "collaboration_history": ["结构化独有合作"],
                "social_events": [
                    {
                        "date": "2026-01-01",
                        "title": "结构化独有事件",
                        "summary": "结构化独有经过",
                    }
                ],
                "tension": "结构化独有张力",
                "trust": 66,
            }
        ],
        "events": [
            {
                "event_id": "evt_test",
                "date": "2026-01-02",
                "title": "结构化独有共同事件",
                "participants": ["npc_01", "npc_02"],
                "summary": "结构化独有共同经过",
                "impact": {
                    "npc_01": "结构化独有影响-陈静",
                    "npc_02": "结构化独有影响-周明远",
                },
            }
        ],
    }
    return world


def test_social_network_injected_with_own_view_only():
    world = _world_with_social_network()

    p1 = pb.build_system_prompt(world, storage.load_npc("npc_01"), {})
    assert "结构化独有看法-陈静" in p1
    assert "结构化独有看法-周明远" not in p1
    assert "结构化独有合作" in p1
    assert "结构化独有事件" in p1
    assert "结构化独有张力" in p1
    assert "结构化独有影响-陈静" in p1
    assert "结构化独有影响-周明远" not in p1

    p2 = pb.build_system_prompt(world, storage.load_npc("npc_02"), {})
    assert "结构化独有看法-周明远" in p2
    assert "结构化独有看法-陈静" not in p2
    assert "结构化独有影响-周明远" in p2
    assert "结构化独有影响-陈静" not in p2


def test_moments_prompt_uses_social_network_and_opinions():
    world = _world_with_social_network()
    npc = storage.load_npc("npc_01")
    prompt = pb.build_moments_messages(world, npc)[0]["content"]

    assert "结构化独有合作" in prompt
    assert "结构化独有事件" in prompt
    assert "结构化独有看法-陈静" in prompt
    assert "结构化独有看法-周明远" not in prompt
    # 原有 opinions_on_colleagues 也应被朋友圈提示词使用
    assert "孙大爷" in prompt
