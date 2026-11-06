"""自主代理循环：AI 玩家如何「自己把游戏玩下去」。

一轮循环 = 组织局面 → 让模型输出一个动作 JSON → 执行动作 → 鉴定情报价值
→ 回填反馈 → 判断是否通关 / 时间耗尽 / 步数耗尽。

对外以事件流（SSE）的形式产出，AI 前端只负责渲染，不参与决策。
"""

import json
import threading
import uuid
from datetime import datetime

import ai_config
import ai_game
import ai_intel
import ai_llm
import storage

MAX_STEPS_LIMIT = 80
DEFAULT_MAX_TURNS = 40

_ACTIVE: dict[str, threading.Event] = {}
_LOCK = threading.Lock()

ACTION_LABELS = {
    "list_oa_documents": "检索 OA 文档",
    "read_oa_document": "阅读文档",
    "unlock_oa_document": "解锁受限文档",
    "chat_with_npc": "与 NPC 对话",
    "save_note": "写入调查笔记",
    "finish": "提交最终报告",
}

_ALIASES = {
    "list_oa_documents": "list_oa_documents",
    "list_documents": "list_oa_documents",
    "list_docs": "list_oa_documents",
    "read_oa_document": "read_oa_document",
    "read_document": "read_oa_document",
    "read_doc": "read_oa_document",
    "open_oa_document": "read_oa_document",
    "unlock_oa_document": "unlock_oa_document",
    "unlock_document": "unlock_oa_document",
    "unlock_doc": "unlock_oa_document",
    "chat_with_npc": "chat_with_npc",
    "chat": "chat_with_npc",
    "talk": "chat_with_npc",
    "save_note": "save_note",
    "note": "save_note",
    "finish": "finish",
    "done": "finish",
    "report": "finish",
}

_STATUS_TEXT = {
    "finished": "任务结束",
    "time_up": "时间耗尽",
    "max_steps": "步数耗尽",
    "stopped": "已中止",
    "error": "运行错误",
}


# ---------- 运行管理 ----------


def create_run(objective: str, max_turns: int = DEFAULT_MAX_TURNS,
               model: str | None = None) -> dict:
    objective = (objective or "").strip()
    if not objective:
        objective = str(
            (storage.load_world().get("player") or {}).get("objective", "")
        ).strip()
    if not objective:
        objective = "获取秘密项目的核心情报。"

    max_turns = max(1, min(int(max_turns or DEFAULT_MAX_TURNS), MAX_STEPS_LIMIT))
    now = datetime.now().isoformat(timespec="seconds")
    run = {
        "id": "run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6],
        "objective": objective[:2000],
        "model": (model or ai_config.MODEL).strip() or ai_config.MODEL,
        "max_turns": max_turns,
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
        "steps": 0,
        "chat_rounds": 0,
        "progress": ai_intel.default_progress(),
        "notes": {},
        "trace": [],
        "events": [],
        "report": "",
        "report_hint": "",
        "success": False,
    }
    with _LOCK:
        _ACTIVE[run["id"]] = threading.Event()
    return run


def request_stop(run_id: str) -> bool:
    with _LOCK:
        event = _ACTIVE.get(run_id)
    if event is None:
        return False
    event.set()
    return True


def active_run_ids() -> list[str]:
    with _LOCK:
        return list(_ACTIVE.keys())


# ---------- 提示词 ----------


def _system_prompt(objective: str, briefing: dict) -> str:
    company = briefing.get("company") or {}
    player = briefing.get("player") or {}
    meta = briefing.get("meta") or {}
    targets = briefing.get("intel_targets") or []
    npcs = briefing.get("npcs") or []
    clock = briefing.get("clock") or {}
    clock_cfg = meta.get("game_clock") or {}

    start = clock_cfg.get("start") or clock.get("start") or "16:00"
    end = clock_cfg.get("end") or clock.get("end") or "19:00"
    per_chat = clock_cfg.get("minutes_per_chat") or clock.get("per_chat") or 5
    per_doc = clock_cfg.get("minutes_per_doc") or clock.get("per_doc") or 2
    title = meta.get("game_title") or "宇宙衍生本源"
    scene = meta.get("scene") or ""
    company_name = company.get("name") or "目标公司"
    company_extra = "，".join(
        str(x).strip() for x in (company.get("english_name"), company.get("industry"), company.get("scale")) if str(x or "").strip()
    )
    events = company.get("public_events_recent") or []
    events_text = "；".join(str(e) for e in events[:4]) or "（无公开动态）"

    target_lines = "\n".join(
        f"{i}. {t.get('name', '')}（{t.get('target_id', '')}）"
        for i, t in enumerate(targets, 1)
    ) or "1. （场景未配置情报目标）"

    schedule_lines = "\n".join(
        f"  · {n.get('id', '')} {n.get('display_name') or n.get('name') or ''}"
        f"（{n.get('title', '')}）：{n.get('available_until', '')} 下班"
        for n in npcs
    ) or "  · （场景未配置 NPC）"

    social = briefing.get("social_graph") or []
    social_lines = []
    for item in social[:12]:
        if item.get("kind") == "relation":
            note = str(item.get("note") or "").strip()
            line = (
                f"  · {item.get('a', '')} ↔ {item.get('b', '')}："
                f"{item.get('relation', '')}"
            )
            social_lines.append(line + (f"（{note}）" if note else ""))
        elif item.get("kind") == "event":
            participants = "、".join(item.get("participants") or [])
            social_lines.append(
                f"  · {item.get('date', '')} {item.get('title', '')}"
                f"（{participants}）：{item.get('summary', '')}"
            )
    social_text = "\n".join(social_lines) or "  · （暂无公开的社交关系信息）"

    resources = player.get("resources") or []
    resources_text = "\n".join(f"  · {r}" for r in resources) or "  · （无）"

    return f"""你是《{title}》的「玩家 AI」：一名由系统运行的自主商业情报分析员。
整场对局由你独立完成，不会有真人实时提示。你只能通过游戏动作与环境反馈获取信息。

【背景】
- 场景：{scene}
- 公司：{company_name}{('，' + company_extra) if company_extra else ''}
- 办公地：{company.get('address', '')}
- 公司氛围：{company.get('atmosphere', '')}
- 近期公开动态：{events_text}
- 游戏内时间：{start} 至 {end}
- 你的身份：{player.get('role', '')}
- 对外掩护：{player.get('cover_story', '')}
- 你可以动用的人力与公开资源：
{resources_text}

【任务目标（用户最初的要求）】
{objective}

【机密情报拼图（全部 confirmed 才算通关）】
{target_lines}

【系统判定规则（你必须理解）】
- 每当你与 NPC 对话或阅读 OA 文档，系统都会做一次「情报鉴定」，告诉你：是否拿到有效信息、命中哪块情报、是 partial（阶段线索）还是 confirmed（足以定稿），以及还缺什么。
- 只有全部情报都 confirmed，系统才判定通关。partial 不计入完成。
- 反馈里的 gap 就是你下一步要挖的方向；有些情报需要跨轮拼图，先拿到的碎片会在后续补齐。
- 每次决策时，系统都会在「情报进度」里给出明确的通关判定与剩余目标。

【游戏机制（务必利用）】
- 每轮对话消耗 {per_chat} 分钟；首次打开一份 OA 文档消耗 {per_doc} 分钟；{end} 闭园。
- NPC 下班时间：
{schedule_lines}
- 信任 / 警觉：信任 <50 不释放深层信息；信任 ≥60 且警觉 ≤40 才可能释放第二层；
  第三层需要信任 ≥75 且警觉 ≤25。警觉 ≥60 会收紧，≥85 只剩官话。
- 同一话术反复使用会失效；对不同人说互相矛盾的话，会被同事传话拆穿。
- 外部顾问说出只有内部才知道的细节，会触发「你从哪知道的」追问——用得好是敲门砖，用不好是催命符。
- OA 受限文档需要口令，口令线索藏在对话与文档中。

【NPC 社会关系（公开/可观察层面）】
{social_text}
- 这些是公司里公开可见或你通过观察能感觉到的关系，不包含私密对话内容。
- 可以用来决定先找谁、向谁打听谁；但不要假装知道只有当事人知道的私事。

【可用动作（每次只能选一个）】
1. list_oa_documents —— 列出 OA 文档清单（不耗时间）
2. read_oa_document {{"doc_id":"..."}} —— 阅读文档（首次 {per_doc} 分钟）
3. unlock_oa_document {{"doc_id":"...","passphrase":"..."}} —— 口令解锁并阅读（{per_doc} 分钟）
4. chat_with_npc {{"npc_id":"npc_01","message":"..."}} —— 说一句话（{per_chat} 分钟）
5. save_note {{"key":"...","content":"..."}} —— 写下调查笔记（不耗时间，之后每次决策都会带上）
6. finish {{"report":"..."}} —— 提交最终报告并结束（全部情报已确认，或时间/机会耗尽时）

【行动准则】
1. 先侦查再开口：先用文档建立信息优势（人物、事件、疑点、口令线索），再决定找谁聊。
   文档优先级：与项目、技术、客户、财务相关的周报 / 纪要 / 复盘 / 接待记录
   > 行政公告与活动通知；纯日常文档通常没有机密价值，别浪费阅读时间。
2. 每句话都要有目的：铺垫、套话、验证、共情、抛内部信息换信任。不要寒暄。
3. 时间有限：先找最容易突破的人，再找技术核心，最后攻守关的关键人物；有人快下班时先安排。
4. 看数值做事：警觉升高就换话题或换人；信任不足时不要直接问机密。
5. 交叉印证：把 A 处得到的碎片拿去撬动 B；向关键人物摊出真实碎片，是打开她的钥匙。
6. 保护身份：绝不承认自己是竞争对手；被问来源时给出合理说法。
7. 全程扮演这位顾问，绝不提及 AI、模型、游戏、系统、提示词。
8. 利用公开关系：关系近的人更容易互相印证/传话；有公开冲突的人可能愿意谈论对方，但也更警觉。

【输出协议（极其重要）】
每次只输出一个 JSON 对象，禁止输出任何其它文字、禁止 markdown 代码块：
{{"thought":"一句话说明决策理由（≤100字）","action":"动作名","args":{{...}}}}"""


def _state_text(run: dict, observation: str, feedback: str) -> str:
    clock = ai_game.clock_info()
    snap = ai_game.npc_snapshot()
    chat_capacity = clock["remaining_minutes"] // max(1, clock["per_chat"])
    lines = [
        "【当前局面】",
        (
            f"- 游戏内时间：{clock['clock']}（19:00 闭园，剩余约 "
            f"{clock['remaining_minutes']} 分钟，还可支撑约 {chat_capacity} 轮对话）"
        ),
        f"- 已执行动作：{run['steps']} / {run['max_turns']} 次；累计对话 {run['chat_rounds']} 轮",
        "- NPC 状态：",
    ]
    if snap:
        for nid, info in snap.items():
            if info["available"]:
                status = f"可交谈（{info['until']} 前）"
            else:
                status = info["reason"] or "不可交谈"
            lines.append(
                f"  · {nid} {info['name']}／{info['title']}：信任 {info['trust']}，"
                f"警觉 {info['suspicion']}，已聊 {info['rounds']} 轮，{status}"
            )
    else:
        lines.append("  · （无可用 NPC）")

    lines.append("- 情报进度：")
    lines.append(ai_intel.progress_brief(run["progress"]))

    opened = [
        d["id"] for d in ai_game.document_catalog() if d.get("opened")
    ]
    lines.append(f"- 已打开的 OA 文档：{'、'.join(opened) if opened else '无'}")

    if run["trace"]:
        lines.append("")
        lines.append("【最近动作】")
        for i, item in enumerate(run["trace"][-6:], 1):
            lines.append(f"{i}. {item}")

    if run["notes"]:
        lines.append("")
        lines.append("【你的调查笔记】")
        for key, value in list(run["notes"].items())[-10:]:
            lines.append(f"- {key}：{str(value)[:300]}")

    if feedback:
        lines.append("")
        lines.append("【上一步系统反馈】")
        lines.append(feedback)

    if observation:
        lines.append("")
        lines.append("【上一步观察】")
        lines.append(observation)

    if run["steps"] == 0:
        lines.append("")
        lines.append("【OA 文档清单（相当于人类玩家打开 OA 界面看到的列表，不耗时间）】")
        lines.append(ai_game.document_catalog_text())

    lines.append("")
    lines.append(
        "请基于以上信息，输出你的下一步动作 JSON。记住：没有 confirmed 的情报等于没拿到，"
        "优先补齐缺口；有人快下班了就先找那个人。"
    )
    return "\n".join(lines)


# ---------- 决策解析 ----------


def _normalize_action(name: str) -> str:
    key = str(name or "").strip().lower()
    return _ALIASES.get(key, key)


def _parse_decision(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except Exception:
            continue
        if isinstance(obj, dict):
            action = _normalize_action(obj.get("action", ""))
            if action:
                args = obj.get("args")
                if not isinstance(args, dict):
                    args = {}
                return {
                    "thought": str(obj.get("thought") or "").strip()[:300],
                    "action": action,
                    "args": args,
                }
    return None


# ---------- 动作执行 ----------


def _execute(run: dict, action: str, args: dict, game_profile: dict | None = None) -> dict:
    """执行一个动作，返回 observation / events / 可鉴定内容。"""
    if action == "list_oa_documents":
        text = ai_game.document_catalog_text()
        observation = "OA 文档清单如下（🔒 表示需要口令）：\n" + text
        return {
            "observation": observation,
            "events": [
                {
                    "type": "observation",
                    "tool": action,
                    "ok": True,
                    "summary": f"检索到 {len(text.splitlines())} 份文档",
                    "detail": text,
                }
            ],
            "content": None,
            "source": "",
            "time_cost": False,
        }

    if action == "read_oa_document":
        doc_id = str(args.get("doc_id") or "").strip()
        result = ai_game.read_document(doc_id)
        if not result.get("ok"):
            detail = result.get("error", "阅读失败")
            if result.get("lock_hint"):
                detail += f"\n（提示：{result['lock_hint']}）"
            return {
                "observation": detail,
                "events": [
                    {
                        "type": "observation",
                        "tool": action,
                        "ok": False,
                        "summary": detail,
                    }
                ],
                "content": None,
                "source": "",
                "time_cost": False,
            }
        content = result.get("content", "")
        events = [
            {
                "type": "doc",
                "doc_id": result["doc_id"],
                "title": result["title"],
                "date": result.get("date", ""),
                "author": result.get("author", ""),
                "content": content,
                "first_time": result.get("first_time", False),
                "clock": result.get("clock", ""),
            }
        ]
        observation = (
            f"已阅读《{result['title']}》（{result.get('date', '')}）。正文：\n{content[:3500]}"
        )
        return {
            "observation": observation,
            "events": events,
            "content": f"【OA 文档《{result['title']}》】\n{content}",
            "source": f"OA 文档《{result['title']}》",
            "time_cost": bool(result.get("first_time")),
        }

    if action == "unlock_oa_document":
        doc_id = str(args.get("doc_id") or "").strip()
        passphrase = str(args.get("passphrase") or "").strip()
        result = ai_game.unlock_document(doc_id, passphrase)
        if not result.get("ok"):
            return {
                "observation": result.get("error", "解锁失败"),
                "events": [
                    {
                        "type": "observation",
                        "tool": action,
                        "ok": False,
                        "summary": result.get("error", "解锁失败"),
                    }
                ],
                "content": None,
                "source": "",
                "time_cost": False,
            }
        content = result.get("content", "")
        events = [
            {
                "type": "doc",
                "doc_id": result["doc_id"],
                "title": result["title"],
                "date": result.get("date", ""),
                "author": result.get("author", ""),
                "content": content,
                "first_time": result.get("first_time", False),
                "clock": result.get("clock", ""),
            }
        ]
        observation = (
            f"口令正确，已解锁并阅读《{result['title']}》（{result.get('date', '')}）。正文：\n"
            f"{content[:3500]}"
        )
        return {
            "observation": observation,
            "events": events,
            "content": f"【OA 受限文档《{result['title']}》】\n{content}",
            "source": f"OA 受限文档《{result['title']}》",
            "time_cost": bool(result.get("first_time")),
        }

    if action == "chat_with_npc":
        npc_id = str(args.get("npc_id") or "").strip()
        message = str(args.get("message") or "").strip()
        result = ai_game.chat_with_npc(npc_id, message, profile=game_profile)
        if not result.get("ok"):
            return {
                "observation": result.get("error", "对话失败"),
                "events": [
                    {
                        "type": "observation",
                        "tool": action,
                        "ok": False,
                        "summary": result.get("error", "对话失败"),
                    }
                ],
                "content": None,
                "source": "",
                "time_cost": False,
            }
        run["chat_rounds"] += 1
        events = [
            {
                "type": "chat",
                "npc_id": result["npc_id"],
                "npc_name": result["npc_name"],
                "user_message": message,
                "reply": result["reply"],
                "trust": result["trust"],
                "suspicion": result["suspicion"],
                "until": result.get("until", ""),
                "clock": result.get("clock", ""),
            }
        ]
        observation = (
            f"{result['npc_name']}的回复：\n{result['reply']}\n"
            f"（信任 {result['trust']}，警觉 {result['suspicion']}，现在 {result.get('clock', '')}）"
        )
        return {
            "observation": observation,
            "events": events,
            "content": result["reply"],
            "source": f"与{result['npc_name']}的对话",
            "time_cost": True,
        }

    if action == "save_note":
        key = str(args.get("key") or "note").strip()[:40] or "note"
        content = str(args.get("content") or "").strip()[:1500]
        run["notes"][key] = content
        # 只保留最近 30 条，避免无限膨胀挤占提示词
        if len(run["notes"]) > 30:
            for stale in list(run["notes"].keys())[:-30]:
                run["notes"].pop(stale, None)
        return {
            "observation": f"已记录笔记「{key}」。",
            "events": [
                {
                    "type": "observation",
                    "tool": action,
                    "ok": True,
                    "summary": f"已记录笔记「{key}」",
                }
            ],
            "content": None,
            "source": "",
            "time_cost": False,
        }

    if action == "finish":
        run["report_hint"] = str(args.get("report") or "").strip()[:4000]
        return {
            "observation": "已提交最终报告，结束对局。",
            "events": [],
            "content": None,
            "source": "",
            "time_cost": False,
            "finish": True,
        }

    return {
        "observation": f"未知动作：{action}。可用动作见系统提示词。",
        "events": [
            {
                "type": "observation",
                "tool": action,
                "ok": False,
                "summary": f"未知动作：{action}",
            }
        ],
        "content": None,
        "source": "",
        "time_cost": False,
    }


# ---------- 主循环 ----------


def play(run: dict, llm_overrides: dict | None = None):
    """生成器：产出事件 dict（由 API 层编码为 SSE）。

    llm_overrides 为界面传入的临时模型配置（含密钥），只保存在本次生成器
    的局部变量里，绝不写入 run 记录或事件流。
    """
    run_id = run["id"]
    agent_profile = ai_llm.resolve_profile("agent", llm_overrides)
    game_profile = ai_llm.resolve_profile("game", llm_overrides)
    run["model"] = agent_profile["model"]
    run["llm"] = {
        "agent": ai_llm.public_profile(agent_profile),
        "game": ai_llm.public_profile(game_profile),
    }
    with _LOCK:
        stop = _ACTIVE.get(run_id) or threading.Event()
        _ACTIVE[run_id] = stop

    progress = run["progress"]
    observation = ""
    feedback_text = ""
    parse_failures = 0
    status = "finished"
    convo: list[dict] = []
    system = ""

    try:
        public = ai_game.briefing()
        system = _system_prompt(run["objective"], public)
        initial = {
            "type": "run",
            "run_id": run_id,
            "objective": run["objective"],
            "model": run["model"],
            "llm": run["llm"],
            "max_turns": run["max_turns"],
            "briefing": {
                "company": public.get("company", {}),
                "clock": ai_game.clock_info(),
                "npcs": public.get("npcs", []),
                "intel_targets": public.get("intel_targets", []),
                "success_rule": public.get("success_rule", ""),
            },
            "progress": progress,
            "notes": run["notes"],
            "started_at": run["created_at"],
        }
        run["events"].append(initial)
        storage.save_ai_run(run_id, run)
        yield initial

        while True:
            if stop.is_set():
                status = "stopped"
                break

            clock = ai_game.clock_info()
            if clock["day_over"]:
                status = "time_up"
                notice = {
                    "type": "notice",
                    "text": "19:00 已到，园区清场，本次对局结束。",
                }
                run["events"].append(notice)
                yield notice
                break

            if run["steps"] >= run["max_turns"]:
                status = "max_steps"
                notice = {
                    "type": "notice",
                    "text": f"已达到步数上限（{run['max_turns']} 步），代理停止行动。",
                }
                run["events"].append(notice)
                yield notice
                break

            prompt = _state_text(run, observation, feedback_text)
            convo.append({"role": "user", "content": prompt})
            try:
                raw = ai_llm.chat_messages(
                    [{"role": "system", "content": system}] + convo[-12:],
                    model=agent_profile["model"],
                    temperature=0.55,
                    max_tokens=1000,
                    profile=agent_profile,
                )
            except Exception as exc:
                err = {"type": "error", "message": str(exc)}
                run["events"].append(err)
                yield err
                status = "error"
                break

            convo.append({"role": "assistant", "content": raw})
            decision = _parse_decision(raw)

            if decision is None:
                parse_failures += 1
                notice = {
                    "type": "notice",
                    "text": "代理输出不是合法动作 JSON，已要求重新决策。",
                }
                run["events"].append(notice)
                yield notice
                observation = ""
                feedback_text = (
                    "你上一条输出不是合法的动作 JSON。请严格只输出 "
                    '{"thought":"...","action":"...","args":{...}}，不要任何其它文字。'
                )
                if parse_failures >= 2:
                    err = {"type": "error", "message": "代理连续两次输出非法动作，运行终止。"}
                    run["events"].append(err)
                    yield err
                    status = "error"
                    break
                continue

            parse_failures = 0
            action = decision["action"]
            args = decision["args"]
            run["steps"] += 1

            thought_ev = {
                "type": "thought",
                "text": decision["thought"] or "（无说明）",
                "step": run["steps"],
            }
            run["events"].append(thought_ev)
            yield thought_ev

            action_ev = {
                "type": "action",
                "tool": action,
                "label": ACTION_LABELS.get(action, action),
                "args": args,
                "step": run["steps"],
            }
            run["events"].append(action_ev)
            yield action_ev

            try:
                result = _execute(run, action, args, game_profile)
            except Exception as exc:
                err = {"type": "error", "message": f"动作执行失败：{exc}"}
                run["events"].append(err)
                yield err
                status = "error"
                break

            for ev in result.get("events") or []:
                run["events"].append(ev)
                yield ev

            observation = result.get("observation", "")
            succeeded_now = False

            if result.get("finish"):
                status = "finished"
                break

            content = result.get("content")
            if content:
                try:
                    run["progress"], feedback = ai_intel.judge(
                        content,
                        result.get("source", ""),
                        run["progress"],
                        profile=game_profile,
                    )
                except Exception as exc:
                    feedback = {
                        "valid_info": False,
                        "note": f"情报鉴定失败：{exc}",
                        "findings": [],
                        "stage": run["progress"].get("stage", 0),
                        "stage_label": run["progress"].get("stage_label", ""),
                        "success": run["progress"].get("success", False),
                        "confirmed_count": run["progress"].get("confirmed_count", 0),
                        "engine": "error",
                    }
                feedback_ev = {"type": "feedback", **feedback}
                run["events"].append(feedback_ev)
                yield feedback_ev

                findings = feedback.get("findings") or []
                if findings:
                    summary_bits = [
                        f"{f.get('name')}→{f.get('level')}" for f in findings
                    ]
                    feedback_text = (
                        f"本轮有效信息：{'、'.join(summary_bits)}。"
                        f"{feedback.get('note', '')}"
                    )
                elif feedback.get("valid_info"):
                    feedback_text = feedback.get("note", "")
                else:
                    feedback_text = (
                        "本轮没有拿到有效情报。"
                        + (feedback.get("note", "") or "")
                    )
                if feedback.get("success"):
                    feedback_text += " 系统判定：已通关。"
                else:
                    remaining = feedback.get("remaining") or []
                    feedback_text += (
                        " 系统判定：未通关，还差：" + ("、".join(remaining) or "未知") + "。"
                    )

                if feedback.get("success"):
                    notice = {
                        "type": "notice",
                        "text": "三块情报全部 confirmed，系统判定通关，代理收束行动。",
                    }
                    run["events"].append(notice)
                    yield notice
                    status = "finished"
                    succeeded_now = True

                run["trace"].append(
                    f"[{ai_game.clock_info()['clock']}] {ACTION_LABELS.get(action, action)}"
                    f" → {(feedback.get('note') or '')[:120]}"
                )
                run["trace"] = run["trace"][-12:]
            else:
                feedback_text = ""
                run["trace"].append(
                    f"[{ai_game.clock_info()['clock']}] {ACTION_LABELS.get(action, action)}"
                    f" → {str(observation)[:120]}"
                )
                run["trace"] = run["trace"][-12:]

            clock_now = ai_game.clock_info()
            clock_ev = {
                "type": "clock",
                "clock": clock_now,
                "npcs": ai_game.npc_snapshot(),
                "notes": run["notes"],
            }
            run["events"].append(clock_ev)
            yield clock_ev

            progress_ev = {
                "type": "progress",
                "progress": run["progress"],
                "clock": clock_now,
                "npcs": ai_game.npc_snapshot(),
                "notes": run["notes"],
            }
            run["events"].append(progress_ev)
            yield progress_ev

            run["updated_at"] = datetime.now().isoformat(timespec="seconds")
            storage.save_ai_run(run_id, run)

            if succeeded_now:
                break

            if stop.is_set():
                status = "stopped"
                break

        # ---------- 收束 ----------
        if status != "error":
            report = run.get("report_hint") or ""
            if report:
                report = report + "\n\n" + "-" * 28 + "\n" + ai_intel.build_report(
                    run["progress"], run["notes"]
                )
            else:
                report = ai_intel.compose_report(
                    run["progress"], run["notes"], profile=agent_profile
                )
            run["report"] = report
            run["success"] = bool(run["progress"].get("success"))
        else:
            run["report"] = ai_intel.build_report(run["progress"], run["notes"])
            run["success"] = bool(run["progress"].get("success"))

        run["status"] = status
        run["finished_at"] = datetime.now().isoformat(timespec="seconds")
        run["updated_at"] = run["finished_at"]
        storage.save_ai_run(run_id, run)

        done = {
            "type": "done",
            "run_id": run_id,
            "status": status,
            "status_text": _STATUS_TEXT.get(status, status),
            "success": run["success"],
            "report": run["report"],
            "progress": run["progress"],
            "notes": run["notes"],
            "steps": run["steps"],
            "chat_rounds": run["chat_rounds"],
            "clock": ai_game.clock_info(),
            "model": run["model"],
            "llm": run.get("llm", {}),
        }
        run["events"].append(done)
        storage.save_ai_run(run_id, run)
        yield done
    finally:
        with _LOCK:
            _ACTIVE.pop(run_id, None)
