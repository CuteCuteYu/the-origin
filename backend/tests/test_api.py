"""API 集成测试（TestClient + 假模型）：不依赖真实 LLM API key。"""

import json

import storage


def _sse_events(text):
    """把 SSE 响应体解析成事件 dict 列表。"""
    events = []
    for frame in text.split("\n\n"):
        line = next((l for l in frame.split("\n") if l.startswith("data:")), None)
        if line:
            events.append(json.loads(line[len("data:"):].strip()))
    return events


# ---------- 只读信息 ----------

def test_briefing_has_no_secret(client):
    res = client.get("/api/game/briefing")
    assert res.status_code == 200
    body = res.json()
    assert body["player"]["role"]
    assert len(body["intel_targets"]) == 3
    assert "499" not in res.text


def test_npc_list_and_initial_state(client):
    npcs = client.get("/api/npcs").json()["npcs"]
    assert len(npcs) == 3
    by_id = {n["id"]: n for n in npcs}
    assert by_id["npc_01"]["available_until"] == "17:30"
    assert by_id["npc_03"]["available_until"] == "19:00"

    state = client.get("/api/game/state").json()
    assert state["clock"] == "16:00" and state["day_over"] is False
    # 初始心理值来自各人设 performance.initial_state
    assert state["npcs"]["npc_01"]["trust"] == 55
    assert state["npcs"]["npc_03"]["trust"] == 25
    assert state["npcs"]["npc_03"]["suspicion"] == 30
    assert state["claims"] == [] and state["notes"] == {}


# ---------- OA 时间成本与解锁 ----------

def test_oa_documents_hide_restricted_content(client):
    docs = client.get("/api/oa/documents").json()["documents"]
    locked = next(d for d in docs if d["id"] == "im_fang_zhou_20261012")
    assert locked["locked"] is True
    assert "blocks" not in locked and "preview" not in locked
    assert "passphrase" not in json.dumps(locked, ensure_ascii=False)
    opened = next(d for d in docs if d["id"] == "im_chen_zhou_20261013")
    assert "blocks" in opened and not opened.get("locked")


def test_oa_unlock_flow(client):
    # 错误口令 → 403，不产生解锁记录，也不推进时钟
    res = client.post(
        "/api/oa/unlock",
        json={"doc_id": "mt_tech_20261012", "passphrase": "wrong"},
    )
    assert res.status_code == 403
    assert client.get("/api/game/state").json()["clock"] == "16:00"

    # 正确口令（大小写与首尾空白归一）；解锁 = 首次阅读，时钟走 2 分钟
    res = client.post(
        "/api/oa/unlock",
        json={"doc_id": "mt_tech_20261012", "passphrase": " alg-14f "},
    )
    assert res.status_code == 200
    body = res.json()
    doc = body["doc"]
    assert doc["locked"] is False and doc["blocks"]
    assert body["clock"] == "16:02"

    # 解锁后文档列表直接可见正文
    docs = client.get("/api/oa/documents").json()["documents"]
    assert next(d for d in docs if d["id"] == "mt_tech_20261012")["blocks"]

    state = client.get("/api/game/state").json()
    assert "mt_tech_20261012" in state["unlocked_docs"]


def test_oa_open_rejects_locked_doc_and_no_double_charge(client):
    # 未解锁直接 open 加密文档 → 403，不计时、不留已读记录
    res = client.post("/api/oa/open", json={"doc_id": "mt_tech_20261012"})
    assert res.status_code == 403
    state = client.get("/api/game/state").json()
    assert state["clock"] == "16:00"
    assert "mt_tech_20261012" not in state["opened_docs"]

    # 解锁（已收 2 分钟）后再 open：不重复计时
    client.post(
        "/api/oa/unlock",
        json={"doc_id": "mt_tech_20261012", "passphrase": "ALG-14F"},
    )
    res = client.post("/api/oa/open", json={"doc_id": "mt_tech_20261012"})
    assert res.status_code == 200
    assert res.json()["clock"] == "16:02"
    assert res.json()["first_time"] is False


def test_oa_open_advances_clock_only_first_time(client):
    first = client.post("/api/oa/open", json={"doc_id": "im_chen_zhou_20261013"}).json()
    assert first["first_time"] is True and first["clock"] == "16:02"
    again = client.post("/api/oa/open", json={"doc_id": "im_chen_zhou_20261013"}).json()
    assert again["first_time"] is False and again["clock"] == "16:02"


# ---------- 对话主流程（SSE） ----------

def test_chat_sse_stream_and_state(client):
    res = client.post("/api/npcs/npc_01/chat", json={"message": "你好，我约了陈静。"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(res.text)
    types = [e["type"] for e in events]
    assert "delta" in types and types[-1] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "delta")

    done = events[-1]
    assert "<state>" not in done["reply"]
    assert done["clock"] == "16:05"                       # 一轮对话 = 5 分钟
    assert done["npc_info"]["trust"] == 62

    # 历史存的是剥离 <state> 后的干净正文；时间戳是游戏内时钟而非机器时间
    msgs = client.get("/api/npcs/npc_01/history").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert "<state>" not in msgs[-1]["content"]
    assert msgs[0]["ts"] == "16:00"      # 开口那一刻
    assert msgs[1]["ts"] == "16:05"      # 回复 = 一轮 5 分钟后

    # 心理状态与口径进入聚合视图
    state = client.get("/api/game/state").json()
    assert state["clock"] == "16:05"
    assert state["npcs"]["npc_01"]["trust"] == 62
    assert state["npcs"]["npc_01"]["suspicion"] == 8
    claim = next(c for c in state["claims"] if "睿析咨询" in c["text"])
    assert claim["ts"] == "16:05"        # 口径时间同样用虚拟时钟


def test_chat_blocked_after_off_work(client):
    storage.save_clock({"minutes": 17 * 60 + 30})  # 陈静 17:30 下班
    res = client.post("/api/npcs/npc_01/chat", json={"message": "在吗？"})
    assert res.status_code == 409
    # 人都不在了，这句话不该落盘
    assert client.get("/api/npcs/npc_01/history").json()["messages"] == []


def test_chat_unknown_npc_404(client):
    res = client.post("/api/npcs/npc_99/chat", json={"message": "hi"})
    assert res.status_code == 404


def test_chat_model_failure_keeps_user_message(client, monkeypatch):
    """模型挂掉时：SSE 发 error 事件，用户这句话仍然真实「说过」。"""
    import llm

    def boom(messages, temperature=0.85, max_tokens=800):
        raise RuntimeError("api down")
        yield ""  # pragma: no cover

    monkeypatch.setattr(llm, "chat_stream", boom)
    res = client.post("/api/npcs/npc_03/chat", json={"message": "你好"})
    events = _sse_events(res.text)
    assert events[-1]["type"] == "error"

    msgs = client.get("/api/npcs/npc_03/history").json()["messages"]
    assert [m["role"] for m in msgs] == ["user"]


# ---------- 笔记与重置 ----------

def test_notes_roundtrip(client):
    res = client.put(
        "/api/game/notes",
        json={"notes": {"general": "记住口令线索", "npc:npc_01": "陈静爱聊快递"}},
    )
    assert res.status_code == 200
    state = client.get("/api/game/state").json()
    assert state["notes"]["general"] == "记住口令线索"
    assert state["notes"]["npc:npc_01"] == "陈静爱聊快递"


def test_reset_restores_initial_state(client):
    client.post("/api/npcs/npc_02/chat", json={"message": "你好"})
    client.put("/api/game/notes", json={"notes": {"general": "手记"}})
    client.post("/api/oa/open", json={"doc_id": "im_chen_zhou_20261013"})

    res = client.post("/api/game/reset")
    assert res.status_code == 200

    state = client.get("/api/game/state").json()
    assert state["clock"] == "16:00"
    assert state["claims"] == [] and state["notes"] == {}
    assert state["unlocked_docs"] == [] and state["opened_docs"] == []
    assert client.get("/api/npcs/npc_02/history").json()["messages"] == []


# ---------- 朋友圈 ----------

def test_moments_generated_then_cached(client, monkeypatch):
    import llm

    payload = {
        "posts": [
            {
                "content": "夜测第 12 天。",
                "likes": ["李星"],
                "comments": [{"from": "赵雯", "text": "辛苦了"}],
            }
        ]
    }
    monkeypatch.setattr(
        llm, "chat", lambda messages, temperature=0.7, max_tokens=800: json.dumps(payload, ensure_ascii=False)
    )

    res = client.get("/api/npcs/npc_02/moments")
    assert res.status_code == 200
    first = res.json()
    assert first["posts"][0]["content"] == "夜测第 12 天。"

    # 第二次命中缓存（generated_at 不变）
    cached = client.get("/api/npcs/npc_02/moments").json()
    assert cached["generated_at"] == first["generated_at"]
