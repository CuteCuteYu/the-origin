"""FastAPI 主入口：路由集中在一个文件里，保持宏观结构简单。"""

import json
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import llm
import storage
from prompt_builder import build_messages, build_moments_messages

app = FastAPI(title="微芒之下 · 后端", version="1.0.0")

# 教学项目：本地前端直连即可，放开 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ---------- 游戏信息 ----------


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


@app.post("/api/game/reset")
def reset_game():
    """清空全部对话存档与朋友圈缓存（AI 的全部记忆），重新开始一局游戏。"""
    removed = storage.reset_all_saves()
    return {"ok": True, "removed_files": removed}


# ---------- OA 模拟系统 ----------


@app.get("/api/oa/documents")
def list_oa_documents():
    """返回 OA 模拟系统的全部文档（公告/纪要/日志/通讯记录/项目档案）。"""
    return {"documents": storage.load_oa_docs()}


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
    """玩家对某个 NPC 说一句话，后端组装分层提示词调用大模型，返回角色回复。"""
    _ensure_npc_exists(npc_id)

    world = storage.load_world()
    npc = storage.load_npc(npc_id)
    history = storage.load_history(npc_id)

    messages = build_messages(world, npc, history, req.message.strip())

    try:
        reply = llm.chat(messages)
    except RuntimeError as e:  # 缺少 API key 等配置问题
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{e}")

    now = datetime.now().isoformat(timespec="seconds")
    history.append({"role": "user", "content": req.message.strip(), "ts": now})
    history.append({"role": "assistant", "content": reply, "ts": now})
    storage.save_history(npc_id, history)

    return {"npc_id": npc_id, "reply": reply}


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
