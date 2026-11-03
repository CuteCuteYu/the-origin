"""storage：JSON 存取、原子写入落盘、目录穿越防护、重置语义。"""

import storage


def test_history_roundtrip_and_default():
    assert storage.load_history("npc_01") == []
    storage.save_history("npc_01", [{"role": "user", "content": "hi"}])
    assert storage.load_history("npc_01")[0]["content"] == "hi"


def test_reset_clears_saves_but_keeps_moments():
    storage.save_history("npc_01", [{"role": "user", "content": "x"}])
    storage.save_npc_state("npc_01", {"trust": 1})
    storage.save_gossip([{"text": "g"}])
    storage.save_claims([{"text": "c"}])
    storage.save_notes({"general": "n"})
    storage.save_moments("npc_01", {"posts": []})
    removed = storage.reset_all_saves()
    assert removed == 5
    assert storage.load_history("npc_01") == []
    assert storage.load_gossip() == []
    assert storage.load_claims() == []
    assert storage.load_notes() == {}
    assert storage.load_npc_state("npc_01") is None
    # 朋友圈缓存不属于对局状态：重置后保留，避免毁掉已生成的 AI 快照
    assert storage.load_moments("npc_01") == {"posts": []}


def test_load_npc_rejects_traversal():
    assert storage.load_npc("npc_01")["meta"]["id"] == "npc_01"
    for bad in ("../world", "../../etc/passwd", "nope", "npc_99"):
        try:
            storage.load_npc(bad)
        except FileNotFoundError:
            continue
        raise AssertionError(f"应当拒绝非法 npc_id：{bad}")


def test_load_oa_docs_merges_all_files_and_sorts():
    docs = storage.load_oa_docs()
    ids = {d["id"] for d in docs}
    assert {"im_fang_zhou_20261012", "mt_tech_20261012", "mt_spm_20261013"} <= ids
    dates = [d["date"] for d in docs]
    assert dates == sorted(dates, reverse=True)


def test_load_world_meta_has_game_clock():
    clock = storage.load_world()["meta"]["game_clock"]
    assert clock["start"] == "16:00"
    assert clock["end"] == "19:00"
    assert clock["minutes_per_chat"] == 5
    assert clock["minutes_per_doc"] == 2
