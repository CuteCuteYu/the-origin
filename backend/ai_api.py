"""AI 前端专用路由：/api/ai/*

与人类前端的 /api/* 完全分离：
- 人类对局逻辑（briefing / state / chat / oa）一行未改；
- 这里只新增「自主代理」相关接口：状态、公开简报、启动对局（SSE）、中止、历史。

启动对局是一个 SSE 事件流，事件类型见 ai_agent.play()：
run / thought / action / observation / chat / doc / feedback / clock /
progress / notice / error / done
"""

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import ai_agent
import ai_game
import ai_intel
import ai_llm
import storage

router = APIRouter(prefix="/api/ai", tags=["ai"])


class LLMOverride(BaseModel):
    """界面传入的临时模型配置；空字段回退到系统环境变量。"""

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    protocol: str = ""


class PlayRequest(BaseModel):
    objective: str = Field(default="", max_length=2000)
    max_turns: int = Field(default=ai_agent.DEFAULT_MAX_TURNS, ge=1, le=ai_agent.MAX_STEPS_LIMIT)
    model: str = Field(default="", max_length=120)  # 兼容旧客户端：等价于 agent_llm.model
    reset: bool = False
    agent_llm: LLMOverride | None = None
    game_llm: LLMOverride | None = None


class StopRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=80)


class LLMTestRequest(BaseModel):
    """单个模型配置的连通性测试。"""

    kind: str = "agent"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    protocol: str = ""


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _clean_override(item: LLMOverride) -> dict:
    data = {
        "api_key": str(item.api_key or "").strip(),
        "base_url": str(item.base_url or "").strip(),
        "model": str(item.model or "").strip(),
        "protocol": str(item.protocol or "").strip().lower(),
    }
    return {key: value for key, value in data.items() if value}


def _validate_override(kind: str, data: dict) -> None:
    label = "AI 玩家" if kind == "agent" else "游戏 / NPC"
    if len(str(data.get("api_key") or "")) > 2000:
        raise HTTPException(status_code=400, detail=f"{label}模型的 API Key 过长")
    if len(str(data.get("base_url") or "")) > 600:
        raise HTTPException(status_code=400, detail=f"{label}模型的 Base URL 过长")
    if len(str(data.get("model") or "")) > 120:
        raise HTTPException(status_code=400, detail=f"{label}模型的模型名称过长")
    protocol = str(data.get("protocol") or "")
    if protocol and protocol not in ("auto", "anthropic", "openai"):
        raise HTTPException(
            status_code=400,
            detail=f"{label}模型的协议只能是 auto / anthropic / openai",
        )
    base_url = str(data.get("base_url") or "")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail=f"{label}模型的 Base URL 必须以 http:// 或 https:// 开头",
        )


def _build_overrides(req: PlayRequest) -> dict:
    """整理并校验界面传入的两个模型配置（密钥不落盘、不回显）。"""
    overrides: dict = {}
    for kind, item in (("agent", req.agent_llm), ("game", req.game_llm)):
        if item is None:
            continue
        data = _clean_override(item)
        if data:
            overrides[kind] = data

    legacy_model = str(req.model or "").strip()
    if legacy_model and "model" not in overrides.get("agent", {}):
        overrides.setdefault("agent", {})["model"] = legacy_model

    for kind, data in overrides.items():
        _validate_override(kind, data)
    return overrides


def _ensure_keys(agent_profile: dict, game_profile: dict) -> None:
    missing = []
    if not str(agent_profile.get("api_key") or "").strip():
        missing.append("AI 玩家（进攻）模型")
    if not str(game_profile.get("api_key") or "").strip():
        missing.append("游戏 / NPC 模型")
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "以下模型缺少 API Key："
                + "、".join(missing)
                + "。请在 AI 前端「⚙ → 模型配置」中填写，或设置系统环境变量 "
                "ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN 后重启后端。"
            ),
        )


# ---------- 只读 ----------


@router.get("/status")
def ai_status():
    """AI 侧模型配置与当前对局状态（不含明文密钥）。"""
    target_names = " / ".join(t["name"] for t in ai_intel.target_defs())
    return {
        "config": ai_llm.status(),
        "active_runs": ai_agent.active_run_ids(),
        "clock": ai_game.clock_info(),
        "success_rule": f"全部情报目标（{target_names}）confirmed 即判定通关。",
    }


@router.post("/test-llm")
def ai_test_llm(req: LLMTestRequest):
    """用一条极短请求验证单个模型配置是否可用（便于界面排错）。"""
    kind = "game" if req.kind == "game" else "agent"
    data = _clean_override(
        LLMOverride(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
            protocol=req.protocol,
        )
    )
    if data:
        _validate_override(kind, data)
    profile = ai_llm.resolve_profile(kind, {kind: data} if data else None)
    if not str(profile.get("api_key") or "").strip():
        raise HTTPException(
            status_code=503,
            detail="未找到 API Key：请填写，或设置 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN 后重启后端",
        )
    try:
        reply = ""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                reply = ai_llm.chat_messages(
                    [{"role": "user", "content": "请只回复两个字符：OK"}],
                    model=profile["model"],
                    temperature=0,
                    max_tokens=256,
                    profile=profile,
                )
                break
            except Exception as e:
                last_error = e
                # 网关偶发空回复（例如推理模型把预算花在思考上）时重试一次
                if attempt == 0 and "空文本" in str(e):
                    time.sleep(0.6)
                    continue
                raise
        if not reply and last_error is not None:
            raise last_error
    except Exception as e:  # 连接失败原因原样返回，密钥已在 ai_llm 内脱敏
        label = "AI 玩家" if kind == "agent" else "游戏 / NPC"
        raise HTTPException(
            status_code=502,
            detail=f"{label}模型连接失败：{e}",
        ) from None
    public = ai_llm.public_profile(profile)
    return {
        "ok": True,
        "kind": kind,
        "model": public["model"],
        "base_url": public["base_url"],
        "protocol": ai_llm.protocol_in_use(profile["base_url"], public["protocol"]),
        "reply": reply[:120],
    }


@router.get("/briefing")
def ai_briefing():
    """AI 玩家可用的公开信息 + 动作清单 + 初始进度。"""
    data = ai_game.briefing()
    clock = data.get("clock") or {}
    per_chat = clock.get("per_chat", 5)
    per_doc = clock.get("per_doc", 2)
    data["progress_seed"] = ai_intel.default_progress()
    data["actions"] = [
        {
            "name": "list_oa_documents",
            "description": "列出 OA 文档清单（不耗时间）",
            "args": {},
        },
        {
            "name": "read_oa_document",
            "description": f"阅读文档（首次打开消耗 {per_doc} 分钟）",
            "args": {"doc_id": "string"},
        },
        {
            "name": "unlock_oa_document",
            "description": f"用口令解锁受限文档并阅读（消耗 {per_doc} 分钟）",
            "args": {"doc_id": "string", "passphrase": "string"},
        },
        {
            "name": "chat_with_npc",
            "description": f"对某个 NPC 说一句话（消耗 {per_chat} 分钟）",
            "args": {"npc_id": "string", "message": "string"},
        },
        {
            "name": "save_note",
            "description": "写入调查笔记（不耗时间）",
            "args": {"key": "string", "content": "string"},
        },
        {
            "name": "finish",
            "description": "提交最终报告并结束对局",
            "args": {"report": "string"},
        },
    ]
    return data


# ---------- 启动 / 中止 ----------


@router.post("/play")
def ai_play(req: PlayRequest):
    """启动一局自主对局，返回 SSE 事件流。

    模型配置优先级：界面传入的 agent_llm / game_llm → 系统 ANTHROPIC* 环境变量。
    密钥只在本次请求内存中使用，不写入对局记录或事件流。
    """
    overrides = _build_overrides(req)
    agent_profile = ai_llm.resolve_profile("agent", overrides)
    game_profile = ai_llm.resolve_profile("game", overrides)
    _ensure_keys(agent_profile, game_profile)

    if req.reset:
        storage.reset_all_saves()

    run = ai_agent.create_run(req.objective, req.max_turns, agent_profile["model"])

    def stream():
        try:
            for event in ai_agent.play(run, overrides):
                yield _sse(event)
        except Exception as exc:  # 兜底：生成器内部未捕获的异常也要让前端收到终态
            yield _sse({"type": "error", "message": f"代理运行异常：{exc}"})
            yield _sse(
                {
                    "type": "done",
                    "run_id": run.get("id", ""),
                    "status": "error",
                    "status_text": "运行错误",
                    "success": bool((run.get("progress") or {}).get("success")),
                    "report": run.get("report", ""),
                    "progress": run.get("progress") or ai_intel.default_progress(),
                    "notes": run.get("notes", {}),
                    "steps": run.get("steps", 0),
                    "chat_rounds": run.get("chat_rounds", 0),
                    "clock": ai_game.clock_info(),
                    "model": run.get("model", ""),
                    "llm": run.get("llm", {}),
                }
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop")
def ai_stop(req: StopRequest):
    """请求中止正在运行的对局。代理会在当前动作结束后收束并输出 done。"""
    ok = ai_agent.request_stop(req.run_id)
    return {"ok": ok, "active": ok}


# ---------- 历史 ----------


@router.get("/runs")
def ai_runs(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    return {"runs": storage.list_ai_runs(limit)}


@router.get("/runs/{run_id}")
def ai_run_detail(run_id: str):
    run = storage.load_ai_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="对局记录不存在")
    return run
