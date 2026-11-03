"""FastAPI 主入口：路由集中在一个文件里，保持宏观结构简单。

对话接口为 SSE 流式响应：
  data: {"type":"delta","text":"..."}   增量正文
  data: {"type":"done",  ...}           一轮结束（含最新时钟 / 心理状态 / 可用性）
  data: {"type":"error","message":"…"}  模型调用失败
"""

import json
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import gamestate
import llm
import storage
from prompt_builder import build_messages, build_moments_messages, build_summary_messages

app = FastAPI(title="微芒之下 · 后端", version="1.1.0")

# 本地开发：前端经 Vite 代理直连，放开 CORS；若部署到公网请改为域名白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class DocOpenRequest(BaseModel):
    doc_id: str = Field(..., min_length=1, max_length=100)


class DocUnlockRequest(BaseModel):
    doc_id: str = Field(..., min_length=1, max_length=100)
    passphrase: str = Field(..., min_length=1, max_length=100)


class NotesPayload(BaseModel):
    notes: dict[str, str] = Field(default_factory=dict)


# 记忆压缩参数：未摘要消息超过 40 条时，把除最近 20 条以外的旧消息压进前情摘要
KEEP_VERBATIM = 20
COMPRESS_THRESHOLD = 40


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ---------- 游戏信息与状态 ----------


@app.get("/api/game/briefing")
def get_briefing():
    """面向玩家的任务简报：世界观公开部分 + 玩家身份与目标。绝不泄露机密项目细节。"""
    world = storage.load_world()
    # 只暴露三个情报点的名称，供前端做"玩家自评"拼图清单；不含任何提示细节
    targets = [
        {"target_id": t.get("target_id"), "name": t.get("name")}
        for t in world.get("secret_project", {}).get("three_intel_targets", [])
    ]
    return {
        "meta": world.get("meta", {}),
        "company": world.get("company", {}),
        "player": world.get("player", {}),
        "intel_targets": targets,
    }


@app.get("/api/game/state")
def get_game_state():
    """聚合运行时状态：虚拟时钟、各 NPC 可用性与心理数值、访客口径、
    玩家笔记、OA 解锁与打开记录。前端启动与每轮对话后刷新。"""
    clock = gamestate.get_clock()
    npcs: dict = {}
    for path in storage.list_npc_files():
        npc_id = path.stem
        try:
            npc = storage.load_npc(npc_id)
        except Exception:
            continue
        avail = gamestate.npc_availability(npc)
        state = gamestate.load_state(npc_id, npc)
        npcs[npc_id] = {
            "available": avail["available"],
            "off_work": avail["off_work"],
            "day_over": avail["day_over"],
            "until": avail["until"],
            "reason": avail["reason"],
            "trust": state["trust"],
            "suspicion": state["suspicion"],
            "rounds": state["rounds"],
        }
    oa = gamestate.oa_state()
    return {
        "clock": clock["clock"],
        "minutes": clock["minutes"],
        "end": clock["end"],
        "day_over": clock["day_over"],
        "npcs": npcs,
        "claims": storage.load_claims(),
        "notes": storage.load_notes(),
        "unlocked_docs": oa["unlocked"],
        "opened_docs": oa["opened"],
    }


@app.post("/api/game/reset")
def reset_game():
    """清空全部运行时状态（对话、心理数值、摘要、八卦、口径、时钟、笔记、
    OA 解锁记录），重新开始一局游戏。朋友圈缓存（moments/）不属于对局
    状态，保留复用——那是 AI 生成的快照，重开一局不必重新花钱生成。"""
    removed = storage.reset_all_saves()
    return {"ok": True, "removed_files": removed}


@app.put("/api/game/notes")
def save_notes(payload: NotesPayload):
    """保存玩家调查笔记（口径备忘 / 人物画像 / 自由手记）。"""
    cleaned: dict[str, str] = {}
    for key, value in payload.notes.items():
        k = str(key).strip()[:60]
        v = str(value or "").strip()[:4000]
        if k:
            cleaned[k] = v
    storage.save_notes(cleaned)
    return {"ok": True, "notes": cleaned}


# ---------- OA 模拟系统 ----------


def _public_doc(doc: dict) -> dict:
    """对外形状：受限文档在解锁前隐去正文与摘要，且绝不外泄口令。"""
    access = doc.get("access") or {}
    if not access.get("restricted"):
        return doc
    doc_id = doc.get("id", "")
    locked = not gamestate.is_doc_unlocked(doc_id)
    item = {k: v for k, v in doc.items() if k not in ("blocks", "preview", "access")}
    item["locked"] = locked
    item["access"] = {k: v for k, v in access.items() if k != "passphrase"}
    if not locked:
        item["blocks"] = doc.get("blocks", [])
        item["preview"] = doc.get("preview", "")
    return item


@app.get("/api/oa/documents")
def list_oa_documents():
    """返回 OA 模拟系统的全部文档。受限文档解锁前只返回元信息（不含 blocks）。"""
    docs = [_public_doc(d) for d in storage.load_oa_docs()]
    return {"documents": docs}


@app.post("/api/oa/open")
def open_oa_document(req: DocOpenRequest):
    """首次打开一份（已解锁的）文档：记录并推进虚拟时钟（翻文件也要花时间）。"""
    docs = {d.get("id"): d for d in storage.load_oa_docs()}
    if req.doc_id not in docs:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc = docs[req.doc_id]
    access = doc.get("access") or {}
    if access.get("restricted") and not gamestate.is_doc_unlocked(req.doc_id):
        # 加密文档必须走口令解锁；直接 open 不计时、不留已读记录
        raise HTTPException(status_code=403, detail="该文档已加密：请先输入口令解锁。")
    first_time = gamestate.mark_opened(req.doc_id)
    clock = gamestate.get_clock()
    if first_time and not clock["day_over"]:
        clock = gamestate.advance_clock(gamestate.clock_cfg()["per_doc"])
    return {
        "ok": True,
        "first_time": first_time,
        "clock": clock["clock"],
        "minutes": clock["minutes"],
        "day_over": clock["day_over"],
    }


@app.post("/api/oa/unlock")
def unlock_oa_document(req: DocUnlockRequest):
    """用口令解锁受限文档。解锁 = 首次阅读，按翻一份文档推进时钟；
    口令错误返回 403（不推进时钟，但现实里别乱试）。"""
    docs = {d.get("id"): d for d in storage.load_oa_docs()}
    doc = docs.get(req.doc_id)
    if doc is None or not (doc.get("access") or {}).get("restricted"):
        raise HTTPException(status_code=404, detail="该文档不存在或无需解锁")
    if not gamestate.check_passphrase(doc, req.passphrase):
        raise HTTPException(status_code=403, detail="口令不对。OA 系统提示：连续错误尝试将被记录。")
    gamestate.mark_unlocked(req.doc_id)
    # 解锁即开始读正文：与普通文档首开一样，收一次「翻文件 2 分钟」时间成本，
    # 否则解锁路径会完全绕开时间经济
    first_time = gamestate.mark_opened(req.doc_id)
    clock = gamestate.get_clock()
    if first_time and not clock["day_over"]:
        clock = gamestate.advance_clock(gamestate.clock_cfg()["per_doc"])
    return {
        "ok": True,
        "doc": _public_doc(doc),
        "clock": clock["clock"],
        "minutes": clock["minutes"],
        "day_over": clock["day_over"],
    }


# ---------- NPC 与对话 ----------


@app.get("/api/npcs")
def list_npcs():
    """返回 NPC 列表（仅展示层信息，绝不返回人设与知识内容）。"""
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
    return {"npcs": npcs}


@app.get("/api/npcs/{npc_id}/history")
def get_history(npc_id: str):
    """读取与某个 NPC 的完整对话历史。"""
    _ensure_npc_exists(npc_id)
    return {"npc_id": npc_id, "messages": storage.load_history(npc_id)}


@app.post("/api/npcs/{npc_id}/chat")
def chat_with_npc(npc_id: str, req: ChatRequest):
    """玩家对某个 NPC 说一句话。SSE 流式返回；一轮 = 游戏内 5 分钟。

    时序：先校验可用性并推进时钟 → 用户消息立刻落盘（模型调用失败这句也
    真实「说过」）→ 流式调用模型 → 解析末尾 <state> 块并沉淀心理状态 /
    八卦 / 口径 → 回传 done 事件。"""
    _ensure_npc_exists(npc_id)

    world = storage.load_world()
    npc = storage.load_npc(npc_id)

    availability = gamestate.npc_availability(npc)
    if not availability["available"]:
        raise HTTPException(status_code=409, detail=availability["reason"])

    pre_clock = gamestate.get_clock()
    clock_info = gamestate.advance_clock(gamestate.clock_cfg()["per_chat"])
    clean_msg = req.message.strip()

    history = storage.load_history(npc_id)
    # 气泡时间戳用游戏内虚拟时钟（开口那一刻 → 5 分钟后的回复），
    # 而非真实机器时间——否则顶栏 16:05、气泡 14:05，非常出戏
    history.append({"role": "user", "content": clean_msg, "ts": pre_clock["clock"]})
    storage.save_history(npc_id, history)

    state = gamestate.load_state(npc_id, npc)
    summary_data = storage.load_summary(npc_id) or {}
    ctx = {
        "clock": clock_info["clock"],
        "state": state,
        "gossip": gamestate.gossip_for(npc_id),
        "claims": gamestate.claims_for(npc_id),
        "summary": summary_data.get("summary", ""),
        "summarized_up_to": summary_data.get("summarized_up_to", 0),
    }
    messages = build_messages(world, npc, history, clean_msg, ctx=ctx)
    meta = npc.get("meta", {})

    def gen():
        chunks: list[str] = []
        try:
            for piece in llm.chat_stream(messages):
                chunks.append(piece)
                yield _sse({"type": "delta", "text": piece})
        except Exception as e:
            yield _sse({"type": "error", "message": f"模型调用失败：{e}"})
            return

        raw = "".join(chunks)
        reply, parsed = gamestate.extract_state(raw)
        if not reply.strip():
            # 极端情况：模型只输出了状态块或空文本
            reply = (raw or "……").strip()

        history.append({"role": "assistant", "content": reply, "ts": clock_info["clock"]})
        storage.save_history(npc_id, history)

        new_state, _, _ = gamestate.apply_round(npc, parsed, clock_str=clock_info["clock"])
        _maybe_compress(npc_id, history)

        clock_now = gamestate.get_clock()
        avail = gamestate.npc_availability(npc)
        yield _sse(
            {
                "type": "done",
                "reply": reply,
                "clock": clock_now["clock"],
                "minutes": clock_now["minutes"],
                "day_over": clock_now["day_over"],
                "npc_info": {
                    "id": npc_id,
                    "name": meta.get("display_name", ""),
                    "available": avail["available"],
                    "off_work": avail["off_work"],
                    "day_over": avail["day_over"],
                    "until": avail["until"],
                    "reason": avail["reason"],
                    "trust": new_state["trust"],
                    "suspicion": new_state["suspicion"],
                    "rounds": new_state["rounds"],
                },
            }
        )

    return StreamingResponse(gen(), media_type="text/event-stream")


def _maybe_compress(npc_id: str, history: list) -> None:
    """旧对话压缩进前情摘要（在 done 事件之后执行，不阻塞用户）。"""
    data = storage.load_summary(npc_id) or {}
    up_to = int(data.get("summarized_up_to", 0) or 0)
    if len(history) - up_to <= COMPRESS_THRESHOLD:
        return
    new_up_to = max(0, len(history) - KEEP_VERBATIM)
    if new_up_to <= up_to:
        return
    batch = history[up_to:new_up_to]
    try:
        summary = llm.chat(
            build_summary_messages(data.get("summary", ""), batch),
            temperature=0.3,
            max_tokens=600,
        )
        summary = gamestate.extract_state(summary)[0].strip()
        if summary:
            storage.save_summary(npc_id, {"summary": summary, "summarized_up_to": new_up_to})
    except Exception:
        pass  # 压缩失败不影响游戏，下次对话结束再试


def _ensure_npc_exists(npc_id: str) -> None:
    if not re.fullmatch(r"npc_\d{2,3}", npc_id):
        raise HTTPException(status_code=404, detail="NPC 不存在")
    try:
        storage.load_npc(npc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="NPC 不存在")


# ---------- 朋友圈（AI 生成 + 本地缓存） ----------


@app.get("/api/npcs/{npc_id}/moments")
def get_moments(npc_id: str):
    """读取某 NPC 的朋友圈；若尚无缓存，则现场调用 AI 生成并缓存。"""
    _ensure_npc_exists(npc_id)
    cached = storage.load_moments(npc_id)
    if cached:
        return cached
    return _generate_moments(npc_id)


@app.post("/api/npcs/{npc_id}/moments/refresh")
def refresh_moments(npc_id: str):
    """重新生成某 NPC 的朋友圈动态（覆盖缓存）。"""
    _ensure_npc_exists(npc_id)
    return _generate_moments(npc_id)


def _generate_moments(npc_id: str) -> dict:
    world = storage.load_world()
    npc = storage.load_npc(npc_id)
    messages = build_moments_messages(world, npc)

    try:
        raw = llm.chat(messages, temperature=0.95, max_tokens=1600)
    except RuntimeError as e:  # 缺少 API key 等配置问题
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"朋友圈生成失败：{e}")

    data = _parse_json_block(raw)
    posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(posts, list) or not posts:
        raise HTTPException(status_code=502, detail="朋友圈生成失败（格式异常），请点击「刷新动态」重试")

    cleaned = []
    for post in posts[:8]:
        if not isinstance(post, dict) or not str(post.get("content", "")).strip():
            continue
        raw_comments = post.get("comments") if isinstance(post.get("comments"), list) else []
        comments = [
            {"from": str(c.get("from", "")).strip(), "text": str(c.get("text", "")).strip()}
            for c in raw_comments
            if isinstance(c, dict) and str(c.get("text", "")).strip()
        ]
        raw_likes = post.get("likes") if isinstance(post.get("likes"), list) else []
        likes = [str(x).strip() for x in raw_likes if str(x).strip()]
        cleaned.append(
            {
                "time": str(post.get("time", "")).strip(),
                "content": str(post.get("content", "")).strip(),
                "likes": likes,
                "comments": comments,
            }
        )

    payload = {
        "npc_id": npc_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "posts": cleaned,
    }
    storage.save_moments(npc_id, payload)
    return payload


def _parse_json_block(text: str):
    """从模型回复中稳健地提取 JSON 对象（容忍代码块包裹与前后杂文）。"""
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None
