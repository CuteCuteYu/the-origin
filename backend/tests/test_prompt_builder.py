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
