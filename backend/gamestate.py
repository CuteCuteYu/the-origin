"""游戏状态机：信任 / 警觉数值、同事传话（八卦）、访客口径、虚拟时钟、OA 解锁。

核心思路：
- NPC 每轮回复末尾携带 <state>{...}</state> 块（由提示词约定），
  后端解析后剥离正文、合并进该 NPC 的心理状态存档；
- 其中 gossip 字段写入共享八卦池，会在之后其他 NPC 的提示词里出现
  （办公室里话是会传的）；
- claims 字段汇入「访客口径清单」，供其他 NPC 交叉比对（说谎会被记住）；
- 虚拟时钟驱动「时间经济」：提问耗 5 分钟、翻文档耗 2 分钟，
  19:00 闭园，各 NPC 有各自的下班时间。
"""

import json
import re
from datetime import datetime

import storage

DEFAULT_TRUST = 40
DEFAULT_SUSPICION = 10

_STATE_RE = re.compile(r"<state>\s*(\{.*?\})\s*</state>", re.S)
# 清理用：任何 <state>…</state> 块（含坏 JSON 的）都不能漏进正文
_STATE_BLOCK_RE = re.compile(r"<state>.*?</state>", re.S | re.I)
# 兜底：模型忘了写闭合标签时，删掉尾部未闭合的 <state>
_STATE_TAIL_RE = re.compile(r"<state>.*\Z", re.S)


# ---------- <state> 块解析 ----------

def extract_state(text: str) -> tuple[str, dict | None]:
    """从模型回复中剥离 <state> 块。

    返回 (干净正文, 解析出的状态 dict 或 None)。模型偶尔会写出多个块或
    坏 JSON——取最后一个可解析的块，正文里所有块（包括坏块、未闭合块）
    都必须移除，绝不能让玩家看到协议残留。
    """
    text = text or ""
    parsed = None
    for raw in _STATE_RE.findall(text):
        try:
            candidate = json.loads(raw)
            if isinstance(candidate, dict):
                parsed = candidate
        except (json.JSONDecodeError, ValueError):
            continue
    clean = _STATE_BLOCK_RE.sub("", text)
    clean = _STATE_TAIL_RE.sub("", clean)
    return clean.rstrip(), parsed


def _clamp(value, default: int) -> int:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, v))


# ---------- NPC 心理状态 ----------

def default_state() -> dict:
    return {
        "trust": DEFAULT_TRUST,
        "suspicion": DEFAULT_SUSPICION,
        "tactics_used": {},
        "rounds": 0,
        "updated_at": None,
    }


def initial_state_for(npc: dict) -> dict:
    """初始心理值可由人设 performance.initial_state 覆盖（守关 BOSS 更警觉）。"""
    state = default_state()
    init = (npc.get("performance") or {}).get("initial_state")
    if isinstance(init, dict):
        state["trust"] = _clamp(init.get("trust"), state["trust"])
        state["suspicion"] = _clamp(init.get("suspicion"), state["suspicion"])
    return state


def load_state(npc_id: str, npc: dict | None = None) -> dict:
    data = storage.load_npc_state(npc_id)
    if data is None:
        return initial_state_for(npc) if npc else default_state()
    # 兼容旧存档 / 缺字段
    state = default_state()
    state.update({k: v for k, v in data.items() if k in state})
    return state


def apply_round(npc: dict, parsed: dict | None, clock_str: str = "") -> tuple[dict, str | None, list]:
    """把本轮模型输出的状态合并进存档，并沉淀八卦与口径。

    返回 (新状态, 本轮新增八卦文本或 None, 本轮新增口径列表)。
    """
    meta = npc.get("meta", {})
    npc_id = meta.get("id", "")
    display_name = meta.get("display_name", npc_id)
    now = datetime.now().isoformat(timespec="seconds")

    state = load_state(npc_id, npc)
    if parsed:
        state["trust"] = _clamp(parsed.get("trust"), state["trust"])
        state["suspicion"] = _clamp(parsed.get("suspicion"), state["suspicion"])
        tactic = str(parsed.get("tactic") or "").strip()
        if tactic and tactic.lower() != "none":
            used = state.get("tactics_used") or {}
            used[tactic] = used.get(tactic, 0) + 1
            state["tactics_used"] = used
    state["rounds"] = int(state.get("rounds", 0)) + 1
    state["updated_at"] = now
    storage.save_npc_state(npc_id, state)

    gossip_text = None
    new_claims: list = []
    if parsed:
        # 八卦：这位 NPC 会跟同事提起访客的内容
        g = str(parsed.get("gossip") or "").strip()
        if g and g.lower() not in ("none", "无", "没有", "没什么"):
            items = storage.load_gossip()
            items.append(
                {
                    "npc_id": npc_id,
                    "from": display_name,
                    "text": g,
                    "clock": clock_str,
                    "ts": now,
                }
            )
            storage.save_gossip(items[-50:])  # 只留最近 50 条
            gossip_text = g

        # 口径：访客对自己身份 / 来意 / 雇主 / 背景的关键陈述
        claims = parsed.get("claims")
        if isinstance(claims, list) and claims:
            all_claims = storage.load_claims()
            existing_texts = {c.get("text") for c in all_claims}
            for c in claims[:3]:
                text = str(c or "").strip()
                if not text or text in existing_texts:
                    continue
                entry = {
                    "text": text,
                    "npc_id": npc_id,
                    "heard_by": display_name,
                    # 与聊天气泡一致：时间戳用游戏内虚拟时钟，出戏的真实时间只在兜底时用
                    "ts": clock_str or now,
                }
                all_claims.append(entry)
                existing_texts.add(text)
                new_claims.append(entry)
            if new_claims:
                storage.save_claims(all_claims[-100:])

    return state, gossip_text, new_claims


def gossip_for(npc_id: str, limit: int = 8) -> list:
    """注入给某 NPC 的八卦：来自其他 NPC（自己说过的已在自己的对话历史里）。"""
    items = [g for g in storage.load_gossip() if g.get("npc_id") != npc_id]
    return items[-limit:]


def claims_for(npc_id: str, limit: int = 12) -> list:
    """注入给某 NPC 的访客口径：其他 NPC 听到的版本。"""
    items = [c for c in storage.load_claims() if c.get("npc_id") != npc_id]
    return items[-limit:]


# ---------- 虚拟时钟 ----------

def _parse_hhmm(text: str, default: int) -> int:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text or "").strip())
    if not m:
        return default
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt_minutes(minutes: int) -> str:
    minutes = max(0, int(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def clock_cfg() -> dict:
    """时钟配置来自 world.json 的 meta.game_clock，缺省 16:00-19:00。"""
    try:
        world = storage.load_world()
        raw = (world.get("meta") or {}).get("game_clock", {}) or {}
    except FileNotFoundError:
        raw = {}
    end = _parse_hhmm(raw.get("end", ""), 19 * 60)
    start = _parse_hhmm(raw.get("start", ""), 16 * 60)
    return {
        "start": start,
        "end": end,
        "per_chat": int(raw.get("minutes_per_chat", 5)),
        "per_doc": int(raw.get("minutes_per_doc", 2)),
    }


def get_clock() -> dict:
    cfg = clock_cfg()
    data = storage.load_clock() or {}
    minutes = int(data.get("minutes", cfg["start"]))
    return {
        "minutes": minutes,
        "clock": fmt_minutes(minutes),
        "start": fmt_minutes(cfg["start"]),
        "end": fmt_minutes(cfg["end"]),
        "day_over": minutes >= cfg["end"],
    }


def advance_clock(delta_minutes: int) -> dict:
    cfg = clock_cfg()
    data = storage.load_clock() or {}
    minutes = int(data.get("minutes", cfg["start"]))
    data["minutes"] = minutes + int(delta_minutes)
    storage.save_clock(data)
    return get_clock()


def npc_availability(npc: dict) -> dict:
    """某 NPC 现在还能不能聊：19:00 闭园 + 各自的下班时间。"""
    meta = npc.get("meta", {})
    cfg = clock_cfg()
    until = _parse_hhmm(meta.get("available_until", ""), cfg["end"])
    clock = get_clock()
    name = meta.get("display_name", "对方")
    if clock["day_over"]:
        return {
            "available": False,
            "off_work": True,
            "day_over": True,
            "until": fmt_minutes(until),
            "reason": "已经过了下班时间，楼里的人陆续走了，今天约不到任何人。",
        }
    if clock["minutes"] >= until:
        return {
            "available": False,
            "off_work": True,
            "day_over": False,
            "until": fmt_minutes(until),
            "reason": f"{name}已经下班离开了（{fmt_minutes(until)} 之后不在）。",
        }
    return {
        "available": True,
        "off_work": False,
        "day_over": False,
        "until": fmt_minutes(until),
        "reason": "",
    }


# ---------- OA 受限文档 ----------

def oa_state() -> dict:
    return storage.load_oa_state()


def is_doc_unlocked(doc_id: str) -> bool:
    return doc_id in oa_state()["unlocked"]


def _norm_passphrase(text: str) -> str:
    return str(text or "").strip().upper()


def check_passphrase(doc: dict, supplied: str) -> bool:
    """校验受限文档口令（忽略大小写与首尾空白）。"""
    access = doc.get("access") or {}
    expected = _norm_passphrase(access.get("passphrase", ""))
    return bool(expected) and _norm_passphrase(supplied) == expected


def mark_unlocked(doc_id: str) -> None:
    state = oa_state()
    if doc_id not in state["unlocked"]:
        state["unlocked"].append(doc_id)
        storage.save_oa_state(state)


def mark_opened(doc_id: str) -> bool:
    """记录「首次打开」（用于时间成本）。返回是否首次。"""
    state = oa_state()
    if doc_id in state["opened"]:
        return False
    state["opened"].append(doc_id)
    storage.save_oa_state(state)
    return True


# ---------- 信任 / 警觉的分档文案（供提示词使用） ----------

def _band(value: int) -> str:
    if value < 25:
        return "极低"
    if value < 50:
        return "偏低"
    if value < 75:
        return "较高"
    return "极高"


def state_summary_for_prompt(state: dict) -> str:
    trust = int(state.get("trust", DEFAULT_TRUST))
    suspicion = int(state.get("suspicion", DEFAULT_SUSPICION))
    tactics = state.get("tactics_used") or {}
    lines = [
        "【你当前对访客的心理状态（系统记录，随对话更新）】",
        f"- 信任度：{trust}/100（{_band(trust)}）　警觉度：{suspicion}/100（{_band(suspicion)}）",
        "数值如何影响你（与信息分层规则配合使用）：",
        "  · 信任不足 50：layer2 及更深的信息不释放，只聊安全话题",
        "  · 信任 ≥ 60 且警觉 ≤ 40：话题命中时机时可以释放 layer2",
        "  · layer3 仅在信任 ≥ 75 且警觉 ≤ 25 时才可能松口",
        "  · 警觉 ≥ 60：即使信任尚可也要收紧信息，按你的警觉反应剧本处理",
        "  · 警觉 ≥ 85：只剩官话与客套，准备体面地结束这场对话",
    ]
    if tactics:
        used = "、".join(f"{k}×{v}" for k, v in tactics.items())
        lines.append(
            f"- 对方已经对你使用过的话术：{used}。同类话术重复次数越多，"
            "你越免疫、越容易起疑——人是会被同一招骗第二次的，但不会被骗第五次。"
        )
    return "\n".join(lines)
