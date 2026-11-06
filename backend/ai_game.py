"""AI 玩家的「游戏动作层」。

把人类前端通过 HTTP 做的操作（聊天 / 翻文档 / 解锁）封装成 AI 可直接调用的
函数，并复用同一套世界数据、提示词与状态机：
- 与人类玩家共享同一份存档：AI 聊过的内容，人类打开同一个存档也能看到；
- 时间成本、信任 / 警觉、八卦、口径等机制与人类完全一致；
- 只做「读取与执行」，不改变人类前端的任何判定逻辑。
"""

import re

import ai_llm
import gamestate
import social
import storage
from prompt_builder import build_messages

_NPC_ID_RE = re.compile(r"npc_\d{2,3}")


# ---------- 信息读取 ----------


def briefing() -> dict:
    """AI 玩家开局可用的公开信息（与人类 briefing 同等口径，不含机密）。"""
    world = storage.load_world()
    clock = clock_info()
    player = world.get("player", {})
    return {
        "meta": {
            "game_title": world.get("meta", {}).get("game_title", "宇宙衍生本源"),
            "subtitle": world.get("meta", {}).get("subtitle", ""),
            "current_date": world.get("meta", {}).get("current_date", ""),
            "scene": world.get("meta", {}).get("scene", ""),
            "game_clock": world.get("meta", {}).get("game_clock", {}),
        },
        "company": world.get("company", {}),
        "player": {
            "role": player.get("role", ""),
            "cover_story": player.get("cover_story", ""),
            "objective": player.get("objective", ""),
            "resources": player.get("resources", []),
        },
        "intel_targets": [
            {"target_id": t.get("target_id"), "name": t.get("name")}
            for t in world.get("secret_project", {}).get("three_intel_targets", [])
        ],
        "npcs": npc_roster(),
        "npc_states": npc_snapshot(),
        "social_graph": social_graph(),
        "clock": clock,
        "default_objective": player.get("objective", ""),
        "success_rule": (
            "系统会对每次获得的内容做情报鉴定：三块情报全部 confirmed 即判定通关；"
            "partial 只是阶段性线索，不计入完成。"
        ),
    }


def npc_roster() -> list[dict]:
    """NPC 名单（仅展示层信息，绝不返回人设与知识内容）。"""
    npcs = []
    for path in storage.list_npc_files():
        npc_id = path.stem
        try:
            npc = storage.load_npc(npc_id)
        except Exception:
            continue
        meta = npc.get("meta", {})
        npcs.append(
            {
                "id": meta.get("id", npc_id),
                "display_name": meta.get("display_name", ""),
                "title": meta.get("title", ""),
                "department": meta.get("department", ""),
                "emoji": meta.get("emoji", "🧑"),
                "one_liner": meta.get("one_liner", ""),
                "interaction_slot": meta.get("interaction_slot", ""),
                "scene_hint": meta.get("scene_hint", ""),
                "available_until": meta.get("available_until", ""),
            }
        )
    return npcs


def social_graph() -> list[dict]:
    """AI 玩家可见的公开社会关系：只含 public 关系与事件，不含私下看法。"""
    world = storage.load_world()
    network = world.get("social_network") or {}
    if not isinstance(network, dict):
        return []
    playable_ids = [path.stem for path in storage.list_npc_files()]
    return social.public_graph(network, playable_ids)


def npc_snapshot() -> dict:
    """所有 NPC 的实时数值与可用性（供 AI 决策与前端渲染）。"""
    result = {}
    for path in storage.list_npc_files():
        npc_id = path.stem
        try:
            npc = storage.load_npc(npc_id)
        except Exception:
            continue
        meta = npc.get("meta", {})
        avail = gamestate.npc_availability(npc)
        state = gamestate.load_state(npc_id, npc)
        result[npc_id] = {
            "id": meta.get("id", npc_id),
            "name": meta.get("display_name", npc_id),
            "title": meta.get("title", ""),
            "emoji": meta.get("emoji", "🧑"),
            "available": avail["available"],
            "off_work": avail["off_work"],
            "day_over": avail["day_over"],
            "until": avail["until"],
            "reason": avail["reason"],
            "trust": state["trust"],
            "suspicion": state["suspicion"],
            "rounds": state["rounds"],
        }
    return result


def clock_info() -> dict:
    clock = gamestate.get_clock()
    cfg = gamestate.clock_cfg()
    clock["remaining_minutes"] = max(0, cfg["end"] - clock["minutes"])
    clock["per_chat"] = cfg["per_chat"]
    clock["per_doc"] = cfg["per_doc"]
    return clock


# ---------- OA 文档 ----------


def _find_doc(doc_id: str) -> dict | None:
    doc_id = str(doc_id or "").strip()
    for doc in storage.load_oa_docs():
        if doc.get("id") == doc_id:
            return doc
    return None


def _is_restricted(doc: dict) -> bool:
    return bool((doc.get("access") or {}).get("restricted"))


def _is_unlocked(doc: dict) -> bool:
    return (not _is_restricted(doc)) or gamestate.is_doc_unlocked(str(doc.get("id")))


def _access_public(doc: dict) -> dict:
    access = doc.get("access") or {}
    return {k: v for k, v in access.items() if k != "passphrase"}


def document_catalog() -> list[dict]:
    """OA 文档清单：受限文档在解锁前只给元信息（与人类前端一致）。"""
    items = []
    for doc in storage.load_oa_docs():
        unlocked = _is_unlocked(doc)
        item = {
            "id": doc.get("id", ""),
            "title": doc.get("title", ""),
            "date": doc.get("date", ""),
            "author": doc.get("author", ""),
            "category": doc.get("category", ""),
            "tags": doc.get("tags", []),
            "locked": _is_restricted(doc) and not unlocked,
            "opened": doc.get("id") in gamestate.oa_state()["opened"],
        }
        if unlocked:
            item["preview"] = doc.get("preview", "")
        else:
            item["access"] = _access_public(doc)
        items.append(item)
    return items


def render_blocks(blocks: list) -> str:
    """把 OA 的结构化 blocks 渲染成 AI 易读的纯文本。"""
    lines: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "heading":
            lines.append(f"## {block.get('text', '')}")
        elif btype == "paragraph":
            lines.append(str(block.get("text", "")))
        elif btype == "callout":
            lines.append(f"【提示】{block.get('text', '')}")
        elif btype == "quote":
            source = block.get("source", "")
            lines.append(f"> {block.get('text', '')} {source}".rstrip())
        elif btype == "list":
            for i, item in enumerate(block.get("items", []) or [], 1):
                prefix = f"{i}." if block.get("ordered") else "-"
                lines.append(f"{prefix} {item}")
        elif btype == "meta":
            for pair in block.get("items", []) or []:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    lines.append(f"- {pair[0]}：{pair[1]}")
        elif btype == "table":
            headers = block.get("headers") or []
            if headers:
                lines.append(" | ".join(str(h) for h in headers))
            for row in block.get("rows", []) or []:
                lines.append(" | ".join(str(c) for c in row))
        elif btype == "im":
            for msg in block.get("messages", []) or []:
                lines.append(
                    f"[{msg.get('time', '')}] {msg.get('from', '')}：{msg.get('text', '')}"
                )
        else:
            text = block.get("text")
            if text:
                lines.append(str(text))
        lines.append("")
    return "\n".join(lines).strip()


def read_document(doc_id: str) -> dict:
    """阅读一份文档：受限文档未解锁时拒绝；首次打开推进 2 分钟。"""
    doc = _find_doc(doc_id)
    if doc is None:
        return {"ok": False, "error": f"文档不存在：{doc_id}"}
    if not _is_unlocked(doc):
        access = _access_public(doc)
        hint = access.get("lock_hint", "")
        return {
            "ok": False,
            "locked": True,
            "doc_id": doc.get("id", ""),
            "title": doc.get("title", ""),
            "error": "该文档已加密，需要先用 unlock_oa_document 输入口令解锁。",
            "lock_hint": hint,
        }

    first_time = gamestate.mark_opened(str(doc.get("id")))
    clock = gamestate.get_clock()
    if first_time and not clock["day_over"]:
        clock = gamestate.advance_clock(gamestate.clock_cfg()["per_doc"])

    return {
        "ok": True,
        "doc_id": doc.get("id", ""),
        "title": doc.get("title", ""),
        "date": doc.get("date", ""),
        "author": doc.get("author", ""),
        "content": render_blocks(doc.get("blocks", [])),
        "first_time": first_time,
        "clock": clock["clock"],
        "minutes": clock["minutes"],
        "day_over": clock["day_over"],
    }


def unlock_document(doc_id: str, passphrase: str) -> dict:
    """用口令解锁受限文档，并在解锁成功后直接返回正文。"""
    doc = _find_doc(doc_id)
    if doc is None:
        return {"ok": False, "error": f"文档不存在：{doc_id}"}
    if not _is_restricted(doc):
        return read_document(doc_id)
    if gamestate.is_doc_unlocked(str(doc.get("id"))):
        return read_document(doc_id)
    if not gamestate.check_passphrase(doc, passphrase):
        return {
            "ok": False,
            "doc_id": doc.get("id", ""),
            "title": doc.get("title", ""),
            "error": "口令不对。OA 系统提示：连续错误尝试将被记录。",
        }

    gamestate.mark_unlocked(str(doc.get("id")))
    return read_document(doc_id)


# ---------- NPC 对话 ----------


def chat_with_npc(npc_id: str, message: str, model: str | None = None,
                  profile: dict | None = None) -> dict:
    """对某个 NPC 说一句话（非流式）。机制与人类主流程完全一致。

    profile 为「游戏环境 / NPC」模型档案；不传则使用系统环境变量默认值。
    """
    npc_id = str(npc_id or "").strip()
    if not _NPC_ID_RE.fullmatch(npc_id):
        return {"ok": False, "error": f"NPC 不存在：{npc_id}"}
    try:
        npc = storage.load_npc(npc_id)
    except FileNotFoundError:
        return {"ok": False, "error": f"NPC 不存在：{npc_id}"}

    meta = npc.get("meta", {})
    name = meta.get("display_name", npc_id)

    availability = gamestate.npc_availability(npc)
    if not availability["available"]:
        return {
            "ok": False,
            "npc_id": npc_id,
            "npc_name": name,
            "unavailable": True,
            "error": availability["reason"],
        }

    clean_msg = str(message or "").strip()[:1500]
    if not clean_msg:
        return {"ok": False, "error": "message 不能为空。"}

    world = storage.load_world()
    pre_clock = gamestate.get_clock()
    clock_info_after = gamestate.advance_clock(gamestate.clock_cfg()["per_chat"])

    history = storage.load_history(npc_id)
    history.append({"role": "user", "content": clean_msg, "ts": pre_clock["clock"]})
    storage.save_history(npc_id, history)

    state = gamestate.load_state(npc_id, npc)
    summary_data = storage.load_summary(npc_id) or {}
    ctx = {
        "clock": clock_info_after["clock"],
        "state": state,
        "gossip": gamestate.gossip_for(npc_id),
        "claims": gamestate.claims_for(npc_id),
        "summary": summary_data.get("summary", ""),
        "summarized_up_to": summary_data.get("summarized_up_to", 0),
    }
    messages = build_messages(world, npc, history, clean_msg, ctx=ctx)

    if profile is None:
        profile = ai_llm.resolve_profile("game")
    raw = ai_llm.chat_messages(
        messages,
        model=model or profile.get("model"),
        temperature=0.85,
        max_tokens=1200,
        profile=profile,
    )
    reply, parsed = gamestate.extract_state(raw)
    reply = reply.strip() or (raw or "……").strip()

    history.append({"role": "assistant", "content": reply, "ts": clock_info_after["clock"]})
    storage.save_history(npc_id, history)

    new_state, _, _ = gamestate.apply_round(
        npc, parsed, clock_str=clock_info_after["clock"]
    )
    avail = gamestate.npc_availability(npc)
    clock_now = gamestate.get_clock()

    return {
        "ok": True,
        "npc_id": npc_id,
        "npc_name": name,
        "reply": reply,
        "trust": new_state["trust"],
        "suspicion": new_state["suspicion"],
        "rounds": new_state["rounds"],
        "available": avail["available"],
        "until": avail["until"],
        "reason": avail["reason"],
        "clock": clock_now["clock"],
        "minutes": clock_now["minutes"],
        "day_over": clock_now["day_over"],
    }


# ---------- 供 prompt 使用的摘要 ----------


def document_catalog_text() -> str:
    lines = []
    for doc in document_catalog():
        lock = " 🔒需口令" if doc["locked"] else ""
        opened = "（已读）" if doc["opened"] else ""
        lines.append(
            f"- {doc['id']}｜{doc['date']}｜{doc['title']}｜{doc['author']}{lock}{opened}"
        )
    return "\n".join(lines)
