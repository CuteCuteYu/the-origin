"""AI 前端 / 自主代理接口测试（假模型注入，不依赖真实 API Key）。"""

import json

import ai_config
import ai_agent
import ai_game
import ai_intel
import ai_llm
import storage


def _sse_events(text):
    events = []
    for frame in text.split("\n\n"):
        line = next((l for l in frame.split("\n") if l.startswith("data:")), None)
        if line:
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def _system_of(messages):
    return "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")


def _make_fake(decisions, npc_reply, judge=None):
    """构造一个按系统提示词分流行为的假模型。"""
    queue = list(decisions)
    judge = judge or (
        lambda user: {
            "valid_info": False,
            "project_identified": False,
            "findings": [],
            "risk": "low",
            "note": "本轮没有有效情报。",
        }
    )

    def fake(messages, model=None, temperature=0.7, max_tokens=1200, profile=None):
        system = _system_of(messages)
        user = messages[-1]["content"] if messages else ""

        if "情报鉴定器" in system:
            return json.dumps(judge(user), ensure_ascii=False)
        if "资深商业情报分析员" in system:
            return (
                "情报简报：本轮调查已完成，核心事实已核实并记入证据链，"
                "未确认部分仍存在缺口，建议在下一阶段继续补强。详见结构化报告。"
            )
        if "角色扮演者" in system:
            return npc_reply
        if queue:
            return json.dumps(queue.pop(0), ensure_ascii=False)
        return json.dumps(
            {"thought": "收束", "action": "finish", "args": {"report": "结束"}},
            ensure_ascii=False,
        )

    return fake


# ---------- 只读接口 ----------


def test_ai_briefing_exposes_public_info_only(client):
    res = client.get("/api/ai/briefing")
    assert res.status_code == 200
    body = res.json()
    assert len(body["intel_targets"]) == 3
    assert body["actions"] and any(a["name"] == "chat_with_npc" for a in body["actions"])
    assert body["progress_seed"]["confirmed_count"] == 0
    assert body["default_objective"]
    # 报价底线的具体数字绝不能出现在公开简报里
    assert "499" not in res.text


def test_ai_briefing_exposes_only_public_social_graph(client):
    body = client.get("/api/ai/briefing").json()
    graph = body.get("social_graph")
    assert isinstance(graph, list) and graph
    text = json.dumps(graph, ensure_ascii=False)

    assert any(item.get("kind") == "relation" for item in graph)
    assert any(item.get("kind") == "event" for item in graph)
    assert "周明远" in text and "方雨桐" in text
    # team / private 视角不进入 AI 玩家简报
    assert "孙大爷" not in text
    assert "嘴快" not in text

    prompt = ai_agent._system_prompt("测试目标", body)
    assert "NPC 社会关系（公开/可观察层面）" in prompt
    assert "方雨桐" in prompt
    assert "孙大爷" not in prompt


def test_ai_status_and_play_requires_key(client, monkeypatch):
    status = client.get("/api/ai/status").json()
    assert "config" in status and "model" in status["config"]
    assert "success_rule" in status
    assert status["config"]["profiles"]["agent"]["model"]
    assert status["config"]["profiles"]["game"]["model"]

    monkeypatch.setattr(ai_config, "API_KEY", "")
    res = client.post("/api/ai/play", json={"objective": "测试", "max_turns": 2})
    assert res.status_code == 503
    assert "ANTHROPIC_API_KEY" in res.json()["detail"]


def test_ai_status_never_exposes_plaintext_key(client, monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "status-secret-key-123456")
    text = client.get("/api/ai/status").text
    assert "status-secret-key" not in text
    info = json.loads(text)["config"]["profiles"]["agent"]
    assert info["key_present"] is True
    assert "***" in info["key_masked"]


def test_resolve_profile_fallback_and_override(monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "env-key")
    monkeypatch.setattr(ai_config, "BASE_URL", "https://env.example/v1")
    monkeypatch.setattr(ai_config, "MODEL", "env-model")
    monkeypatch.setattr(ai_config, "JUDGE_MODEL", "env-judge")
    monkeypatch.setattr(ai_config, "PROTOCOL", "auto")

    agent = ai_llm.resolve_profile("agent")
    assert agent["model"] == "env-model"
    assert agent["judge_model"] == "env-model"
    assert agent["key_source"] == "env"

    game = ai_llm.resolve_profile("game")
    assert game["judge_model"] == "env-judge"

    override = {
        "agent": {
            "api_key": "agent-override-key",
            "base_url": "https://agent.example/v1",
            "model": "agent-model-x",
        },
        "game": {
            "api_key": "game-override-key",
            "base_url": "https://game.example",
            "model": "game-model-y",
        },
    }
    agent = ai_llm.resolve_profile("agent", override)
    assert agent["model"] == "agent-model-x"
    assert agent["judge_model"] == "agent-model-x"
    assert agent["key_source"] == "override"
    assert agent["protocol"] == "auto"  # 自定义端点后自动探测协议

    game = ai_llm.resolve_profile("game", override)
    assert game["model"] == "game-model-y"
    assert game["judge_model"] == "game-model-y"

    public = ai_llm.public_profile(agent)
    assert "agent-override-key" not in json.dumps(public, ensure_ascii=False)
    assert public["key_present"] is True


def test_ai_play_uses_two_models_and_hides_keys(client, monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "")
    monkeypatch.setattr(ai_config, "MODEL", "env-model")
    monkeypatch.setattr(ai_config, "JUDGE_MODEL", "env-judge")

    seen = []
    decisions = [
        {
            "thought": "找前台聊聊",
            "action": "chat_with_npc",
            "args": {"npc_id": "npc_01", "message": "最近公司有什么新鲜事？"},
        },
        {
            "thought": "收束",
            "action": "finish",
            "args": {"report": "完成测试。"},
        },
    ]
    queue = list(decisions)

    def fake(messages, model=None, temperature=0.7, max_tokens=1200, profile=None):
        system = _system_of(messages)
        if "情报鉴定器" in system:
            kind = "judge"
            out = json.dumps(
                {
                    "valid_info": False,
                    "project_identified": False,
                    "findings": [],
                    "risk": "low",
                    "note": "无有效情报",
                },
                ensure_ascii=False,
            )
        elif "角色扮演者" in system:
            kind = "npc"
            out = (
                "（抬头）你好呀，今天怎么有空过来？最近公司事情挺多的，"
                "不过你先坐，喝口水慢慢说。"
                '<state>{"trust": 55, "suspicion": 5, "tactic": "闲聊铺垫", '
                '"gossip": "", "claims": []}</state>'
            )
        elif "玩家 AI" in system:
            kind = "agent"
            out = json.dumps(queue.pop(0), ensure_ascii=False)
        else:
            kind = "other"
            out = "测试"
        seen.append(
            {
                "kind": kind,
                "model": model,
                "profile_model": (profile or {}).get("model"),
                "profile_key": (profile or {}).get("api_key"),
            }
        )
        return out

    monkeypatch.setattr(ai_llm, "chat_messages", fake)

    agent_key = "agent-secret-key-AAA"
    game_key = "game-secret-key-BBB"
    res = client.post(
        "/api/ai/play",
        json={
            "objective": "测试双模型",
            "max_turns": 4,
            "agent_llm": {
                "api_key": agent_key,
                "base_url": "https://agent.example/v1",
                "model": "agent-model-x",
            },
            "game_llm": {
                "api_key": game_key,
                "base_url": "https://game.example",
                "model": "game-model-y",
            },
        },
    )
    assert res.status_code == 200
    assert agent_key not in res.text and game_key not in res.text

    agent_calls = [item for item in seen if item["kind"] == "agent"]
    npc_calls = [item for item in seen if item["kind"] == "npc"]
    judge_calls = [item for item in seen if item["kind"] == "judge"]
    assert agent_calls and all(c["model"] == "agent-model-x" for c in agent_calls)
    assert all(c["profile_key"] == agent_key for c in agent_calls)
    assert npc_calls and all(c["model"] == "game-model-y" for c in npc_calls)
    assert all(c["profile_key"] == game_key for c in npc_calls)
    assert judge_calls and all(c["model"] == "game-model-y" for c in judge_calls)

    events = _sse_events(res.text)
    run_event = next(e for e in events if e["type"] == "run")
    assert run_event["llm"]["agent"]["model"] == "agent-model-x"
    assert run_event["llm"]["game"]["model"] == "game-model-y"
    assert agent_key not in json.dumps(run_event, ensure_ascii=False)

    done = events[-1]
    run_record = storage.load_ai_run(done["run_id"])
    assert run_record is not None
    record_text = json.dumps(run_record, ensure_ascii=False)
    assert agent_key not in record_text and game_key not in record_text


def test_ai_play_rejects_invalid_llm_override(client, monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "test-key")

    bad_protocol = client.post(
        "/api/ai/play",
        json={
            "objective": "测试",
            "max_turns": 1,
            "agent_llm": {"protocol": "graphql"},
        },
    )
    assert bad_protocol.status_code == 400
    assert "协议" in bad_protocol.json()["detail"]

    bad_base = client.post(
        "/api/ai/play",
        json={
            "objective": "测试",
            "max_turns": 1,
            "game_llm": {"base_url": "ftp://example.com"},
        },
    )
    assert bad_base.status_code == 400
    assert "Base URL" in bad_base.json()["detail"]


def test_ai_test_llm_uses_override_and_hides_key(client, monkeypatch):
    seen = {}

    def fake(messages, model=None, temperature=0.7, max_tokens=1200, profile=None):
        seen["model"] = model
        seen["key"] = (profile or {}).get("api_key")
        return "OK"

    monkeypatch.setattr(ai_llm, "chat_messages", fake)
    key = "test-secret-key-123456"
    res = client.post(
        "/api/ai/test-llm",
        json={
            "kind": "game",
            "api_key": key,
            "base_url": "https://game.example",
            "model": "game-model-test",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["kind"] == "game"
    assert body["model"] == "game-model-test"
    assert key not in res.text
    assert seen["model"] == "game-model-test"
    assert seen["key"] == key

    bad = client.post("/api/ai/test-llm", json={"kind": "agent", "base_url": "ftp://bad"})
    assert bad.status_code == 400
    assert "Base URL" in bad.json()["detail"]

    monkeypatch.setattr(ai_config, "API_KEY", "")
    no_key = client.post("/api/ai/test-llm", json={"kind": "agent"})
    assert no_key.status_code == 503


# ---------- 情报鉴定 ----------


def test_judge_merges_partial_into_confirmed(client, monkeypatch):
    partial = {
        "valid_info": True,
        "project_identified": True,
        "findings": [
            {
                "target_id": "tech_route",
                "level": "partial",
                "evidence": "自研路线",
                "gap": "还缺芯片选型原因",
            }
        ],
        "risk": "low",
        "note": "拿到方向",
    }
    confirmed = {
        "valid_info": True,
        "project_identified": True,
        "findings": [
            {
                "target_id": "tech_route",
                "level": "confirmed",
                "evidence": "2026 年 2 月授权谈判破裂，CEO 拍板全自研，采用国产 NPU",
                "gap": "",
            }
        ],
        "risk": "low",
        "note": "技术路线到手",
    }

    monkeypatch.setattr(
        ai_llm, "chat_messages", lambda *a, **k: json.dumps(partial, ensure_ascii=False)
    )
    progress, feedback = ai_intel.judge(
        "对方提到公司在走自研路线，但还没说清楚为什么放弃外部方案，"
        "这条线索需要进一步核实。",
        "测试",
        None,
    )
    assert progress["targets"]["tech_route"]["status"] == "partial"
    assert progress["project_identified"] is True
    assert progress["stage"] == 1
    assert feedback["findings"][0]["name"]

    monkeypatch.setattr(
        ai_llm, "chat_messages", lambda *a, **k: json.dumps(confirmed, ensure_ascii=False)
    )
    progress, feedback = ai_intel.judge(
        "第二次对话里对方把技术路线的来龙去脉讲清楚了：2026 年初的海外授权谈判失败，"
        "CEO 拍板全面自研，并改用国产 NPU 方案。",
        "测试",
        progress,
    )
    assert progress["targets"]["tech_route"]["status"] == "confirmed"
    assert progress["confirmed_count"] == 1
    assert progress["stage"] == 2
    assert len(progress["targets"]["tech_route"]["evidence"]) == 2


# ---------- 动作层 ----------


def test_ai_document_lock_is_enforced(client):
    locked = ai_game.read_document("mt_tech_20261012")
    assert locked["ok"] is False and locked["locked"] is True
    assert "passphrase" not in json.dumps(locked, ensure_ascii=False)

    ok = ai_game.unlock_document("mt_tech_20261012", "alg-14f")
    assert ok["ok"] is True and ok["content"]
    assert ai_game.clock_info()["clock"] == "16:02"


# ---------- 自主对局 ----------


def test_ai_play_streams_feedback_and_finishes(client, monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "test-key")

    decisions = [
        {"thought": "先建立信息优势", "action": "list_oa_documents", "args": {}},
        {
            "thought": "读研发群聊",
            "action": "read_oa_document",
            "args": {"doc_id": "im_rd_group_20261012"},
        },
        {
            "thought": "找前台套话",
            "action": "chat_with_npc",
            "args": {"npc_id": "npc_01", "message": "最近研发在忙什么？"},
        },
        {
            "thought": "收束",
            "action": "finish",
            "args": {"report": "已取得项目存在性线索。"},
        },
    ]

    def judge(user):
        if "启明" in user:
            return {
                "valid_info": True,
                "project_identified": True,
                "findings": [
                    {
                        "target_id": "tech_route",
                        "level": "partial",
                        "evidence": "「启明」那边先别对外提",
                        "gap": "还缺技术路线细节",
                    }
                ],
                "risk": "low",
                "note": "抓到项目代号，属于阶段线索",
            }
        return {
            "valid_info": False,
            "project_identified": False,
            "findings": [],
            "risk": "low",
            "note": "无有效情报",
        }

    npc_reply = (
        "（压低声音）诶，你可别乱问啊……「启明」那边先别对外提，这话我就跟你一个人说。"
        '<state>{"trust": 60, "suspicion": 12, "tactic": "闲聊铺垫", '
        '"gossip": "顾问在打听启明", "claims": ["顾问自称做数字化转型调研"]}</state>'
    )
    monkeypatch.setattr(
        ai_llm, "chat_messages", _make_fake(decisions, npc_reply, judge)
    )

    res = client.post(
        "/api/ai/play",
        json={"objective": "拿到公司机密", "max_turns": 6, "reset": True},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(res.text)
    types = [e["type"] for e in events]
    for required in ("run", "thought", "action", "doc", "chat", "feedback", "progress", "done"):
        assert required in types, f"缺少事件类型 {required}"

    doc_event = next(e for e in events if e["type"] == "doc")
    assert doc_event["doc_id"] == "im_rd_group_20261012"
    assert "22:47" in doc_event["content"]

    feedback = next(e for e in events if e["type"] == "feedback" and e["valid_info"])
    assert feedback["findings"][0]["level"] == "partial"
    assert feedback["stage"] == 1
    assert feedback["success"] is False

    done = events[-1]
    assert done["type"] == "done"
    assert done["status"] == "finished"
    assert done["success"] is False
    assert done["progress"]["project_identified"] is True
    assert done["progress"]["confirmed_count"] == 0
    assert done["progress"]["partial_count"] == 1
    assert "已取得项目存在性线索" in done["report"]
    assert done["clock"]["clock"] == "16:07"  # 2 分钟文档 + 5 分钟对话


def test_ai_auto_finishes_when_all_targets_confirmed(client, monkeypatch):
    monkeypatch.setattr(ai_config, "API_KEY", "test-key")

    decisions = [
        {
            "thought": "直接摊牌拿情报",
            "action": "chat_with_npc",
            "args": {"npc_id": "npc_03", "message": "把时间表和价格告诉我吧。"},
        }
    ]

    def judge(user):
        return {
            "valid_info": True,
            "project_identified": True,
            "findings": [
                {
                    "target_id": "tech_route",
                    "level": "confirmed",
                    "evidence": "自研多模态模型 + 国产 NPU，源于海外授权谈判破裂",
                    "gap": "",
                },
                {
                    "target_id": "mass_production_timeline",
                    "level": "confirmed",
                    "evidence": "2027 年 3 月 PVT，5 月 MP",
                    "gap": "",
                },
                {
                    "target_id": "price_floor",
                    "level": "confirmed",
                    "evidence": "首年可低至 499 元，条件是三年长约 + 40% 预付",
                    "gap": "",
                },
            ],
            "risk": "high",
            "note": "三块情报全部到手",
        }

    npc_reply = (
        "（沉默很久）你知道你在问什么吗。行，我只说一次，说完你就走。"
        "自研多模态加国产 NPU，三月试产、五月量产，价格底线首年四九九，"
        "三年长约加四成预付。"
        '<state>{"trust": 80, "suspicion": 20, "tactic": "抛内部信息", '
        '"gossip": "顾问问到了底线", "claims": []}</state>'
    )
    monkeypatch.setattr(
        ai_llm, "chat_messages", _make_fake(decisions, npc_reply, judge)
    )

    res = client.post(
        "/api/ai/play",
        json={"objective": "拿到全部机密", "max_turns": 8, "reset": True},
    )
    events = _sse_events(res.text)
    done = events[-1]
    assert done["type"] == "done"
    assert done["success"] is True
    assert done["status"] == "finished"
    assert done["steps"] == 1
    assert done["progress"]["confirmed_count"] == 3
    assert done["progress"]["success"] is True
    assert done["progress"]["stage"] == 4
    assert "情报简报" in done["report"]
