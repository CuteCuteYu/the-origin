"""gamestate：<state> 解析、心理状态合并、八卦 / 口径沉淀、虚拟时钟、OA 解锁。"""

import gamestate
import storage


def _npc(npc_id="npc_01"):
    return storage.load_npc(npc_id)


# ---------- <state> 块解析 ----------

def test_extract_state_basic():
    clean, parsed = gamestate.extract_state('你好。<state>{"trust": 70}</state>')
    assert clean == "你好。"
    assert parsed == {"trust": 70}


def test_extract_state_takes_last_parseable_and_strips_all():
    text = (
        "a<state>{\"trust\": 1}</state>b"
        "<state>bad json</state>c"
        "<state>{\"trust\": 9}</state>"
    )
    clean, parsed = gamestate.extract_state(text)
    assert "<state>" not in clean
    assert parsed == {"trust": 9}


def test_extract_state_none_when_missing():
    clean, parsed = gamestate.extract_state("普通回复")
    assert clean == "普通回复"
    assert parsed is None


def test_extract_state_strips_unclosed_block():
    """模型忘了写闭合标签：尾部整块截掉，玩家看不到协议残留。"""
    clean, parsed = gamestate.extract_state('你好。<state>{"trust": 70')
    assert clean == "你好。"
    assert parsed is None


# ---------- 心理状态与沉淀 ----------

def test_apply_round_merges_clamps_and_persists():
    parsed = {
        "trust": 200,          # 越界 → 截到 100
        "suspicion": -3,       # 越界 → 截到 0
        "tactic": "套近乎",
        "gossip": "访客问了门禁的事",
        "claims": ["自称睿析咨询", "自称睿析咨询", ""],  # 去重 + 去空
    }
    state, gossip, claims = gamestate.apply_round(_npc(), parsed, clock_str="16:05")

    assert state["trust"] == 100 and state["suspicion"] == 0
    assert state["tactics_used"] == {"套近乎": 1}
    assert state["rounds"] == 1
    assert gossip == "访客问了门禁的事"
    assert len(claims) == 1 and claims[0]["text"] == "自称睿析咨询"

    # 状态 / 八卦 / 口径全部落盘可回读
    reloaded = gamestate.load_state("npc_01", _npc())
    assert reloaded["trust"] == 100 and reloaded["rounds"] == 1
    assert storage.load_gossip()[-1]["npc_id"] == "npc_01"
    assert storage.load_claims()[-1]["heard_by"] == "陈静"


def test_apply_round_tactic_reuse_accumulates():
    for _ in range(3):
        gamestate.apply_round(_npc(), {"tactic": "示弱", "trust": 50})
    state = gamestate.load_state("npc_01", _npc())
    assert state["tactics_used"]["示弱"] == 3


def test_apply_round_without_state_still_counts_round():
    state, gossip, claims = gamestate.apply_round(_npc(), None)
    assert state["rounds"] == 1
    assert gossip is None and claims == []


def test_gossip_and_claims_exclude_own_npc():
    gamestate.apply_round(_npc("npc_01"), {"gossip": "G1", "claims": ["C1"]})
    gamestate.apply_round(_npc("npc_02"), {"gossip": "G2", "claims": ["C2"]})

    assert [g["text"] for g in gamestate.gossip_for("npc_01")] == ["G2"]
    assert [c["text"] for c in gamestate.claims_for("npc_01")] == ["C2"]
    assert [g["text"] for g in gamestate.gossip_for("npc_03")] == ["G1", "G2"]


def test_neutral_gossip_words_not_saved():
    _, gossip, _ = gamestate.apply_round(_npc(), {"gossip": "没有"})
    assert gossip is None
    assert storage.load_gossip() == []


# ---------- 虚拟时钟 ----------

def test_clock_defaults_and_advance():
    c = gamestate.get_clock()
    assert c["clock"] == "16:00" and c["day_over"] is False
    c = gamestate.advance_clock(5)
    assert c["clock"] == "16:05"
    storage.save_clock({"minutes": 19 * 60})
    assert gamestate.get_clock()["day_over"] is True


def test_npc_availability_off_work_boundaries():
    npc = _npc("npc_01")  # 陈静 17:30 下班
    storage.save_clock({"minutes": 17 * 60 + 25})
    assert gamestate.npc_availability(npc)["available"] is True

    storage.save_clock({"minutes": 17 * 60 + 30})
    info = gamestate.npc_availability(npc)
    assert info["available"] is False and info["off_work"] is True
    assert "下班" in info["reason"] and info["day_over"] is False

    storage.save_clock({"minutes": 19 * 60})
    assert gamestate.npc_availability(npc)["day_over"] is True


# ---------- OA 解锁 ----------

def test_passphrase_normalized():
    doc = {"id": "x", "access": {"passphrase": "VIGANEX2021"}}
    assert gamestate.check_passphrase(doc, " viganex2021 ") is True
    assert gamestate.check_passphrase(doc, "VIGANEX2020") is False
    # 没设口令的文档一律拒绝
    assert gamestate.check_passphrase({"access": {}}, "any") is False


def test_unlock_and_open_records():
    assert gamestate.mark_opened("d1") is True
    assert gamestate.mark_opened("d1") is False  # 只有首次才算时间成本
    gamestate.mark_unlocked("d2")
    assert gamestate.is_doc_unlocked("d2") is True
    assert gamestate.is_doc_unlocked("d1") is False


# ---------- 提示词层 ----------

def test_state_summary_mentions_gates_and_tactics():
    text = gamestate.state_summary_for_prompt(
        {"trust": 80, "suspicion": 20, "tactics_used": {"共情": 2}}
    )
    assert "信任 ≥ 60" in text
    assert "警觉 ≥ 85" in text
    assert "共情×2" in text
