"""面向 AI 前端的「情报鉴定与阶段反馈」引擎。

人类前端没有胜负判定（由玩家自己判断），而 AI 需要一个明确信号：
每次 NPC 对话 / OA 文档阅读后，本模块判断这段内容是否带来有效情报、
命中了三块目标中的哪一块、是阶段线索（partial）还是足以定稿（confirmed），
并据此推进全局阶段。三块全部 confirmed 即判定通关。

判定优先走大模型（用 world.json 里的真值做评分标准），
模型不可用时退化为关键词启发式，保证 AI 端永远能拿到反馈。
"""

import copy
import json
import re
from datetime import datetime

import ai_llm
import storage

DEFAULT_TARGET_IDS = ("tech_route", "mass_production_timeline", "price_floor")

_TARGET_NAMES = {
    "tech_route": "技术路线",
    "mass_production_timeline": "量产时间表",
    "price_floor": "报价底线",
}

LEVEL_RANK = {"unknown": 0, "partial": 1, "confirmed": 2}
STATUS_LABELS = {"unknown": "未获取", "partial": "部分线索", "confirmed": "已确认"}

STAGE_LABELS = {
    0: "侦查阶段 · 尚未确认秘密项目存在",
    1: "情报拼图 · 已确认秘密项目存在",
    2: "情报拼图 · 1/3 已确认",
    3: "关键阶段 · 2/3 已确认",
    4: "任务达成 · 3/3 已确认",
}

# 关键词兜底（仅在模型鉴定失败时使用；场景配置可通过 targets[].keywords 覆盖）
_HINTS = {
    "tech_route": ["自研", "多模态", "国产芯片", "NPU", "授权", "谈判", "技术路线", "架构", "精度"],
    "mass_production_timeline": ["2027", "三月", "PVT", "试产", "量产", "MP", "时间表", "节点", "Q2"],
    "price_floor": ["499", "报价", "底线", "预付", "长约", "三年", "899", "让价", "首年"],
}


# ---------- 结构 ----------


def _world() -> dict:
    try:
        return storage.load_world()
    except Exception:
        return {}


def _derive_hints(name: str, detail: str) -> list[str]:
    """为自定义场景推导关键词：名称 + 引号短语 + 数字。"""
    hints: list[str] = []
    if name:
        hints.append(name)
    for match in re.findall(r"「([^」]{1,16})」", detail or ""):
        hints.append(match)
    for match in re.findall(r"\d{2,4}", detail or ""):
        hints.append(match)
    seen = set()
    result = []
    for hint in hints:
        hint = hint.strip()
        if hint and hint not in seen:
            seen.add(hint)
            result.append(hint)
    return result[:12]


def target_defs() -> list[dict]:
    """从世界观读取情报目标（含仅供鉴定器使用的真值细节与关键词）。"""
    world = _world()
    raw = (world.get("secret_project") or {}).get("three_intel_targets", [])
    defs: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("target_id") or "").strip()
        if not tid:
            continue
        name = str(item.get("name") or _TARGET_NAMES.get(tid, tid))
        detail = str(item.get("detail") or "")
        raw_keywords = item.get("keywords")
        keywords = (
            [str(k).strip() for k in raw_keywords if str(k).strip()]
            if isinstance(raw_keywords, list)
            else []
        )
        if not keywords:
            keywords = list(_HINTS.get(tid, [])) or _derive_hints(name, detail)
        defs.append(
            {
                "target_id": tid,
                "name": name,
                "detail": detail,
                "hint": str(item.get("hint") or ""),
                "keywords": keywords,
            }
        )
    if not defs:
        for tid in DEFAULT_TARGET_IDS:
            defs.append(
                {
                    "target_id": tid,
                    "name": _TARGET_NAMES[tid],
                    "detail": "",
                    "hint": "",
                    "keywords": list(_HINTS[tid]),
                }
            )
    return defs


def target_ids() -> tuple[str, ...]:
    ids = tuple(t["target_id"] for t in target_defs())
    return ids or DEFAULT_TARGET_IDS


def public_targets() -> list[dict]:
    """对外（AI 玩家可见）只给名称，不给真值与提示。"""
    return [
        {"target_id": t["target_id"], "name": t["name"]}
        for t in target_defs()
    ]


def default_progress() -> dict:
    ids = target_ids()
    return {
        "targets": {
            tid: {"status": "unknown", "evidence": [], "gap": "", "updated_at": None}
            for tid in ids
        },
        "project_identified": False,
        "stage": 0,
        "stage_label": STAGE_LABELS[0],
        "success": False,
        "confirmed_count": 0,
        "partial_count": 0,
        "total_count": len(ids),
        "updated_at": None,
    }


def progress_brief(progress: dict) -> str:
    """把进度渲染成给 AI 玩家看的紧凑文本。"""
    p = progress or default_progress()
    defs = target_defs()
    names = {t["target_id"]: t["name"] for t in defs}
    ids = tuple(t["target_id"] for t in defs)
    lines = []
    for tid in ids:
        entry = (p.get("targets") or {}).get(tid) or {}
        status = entry.get("status", "unknown")
        line = f"  · {names[tid]}：{STATUS_LABELS.get(status, status)}"
        if entry.get("gap"):
            line += f"（缺口：{entry['gap']}）"
        lines.append(line)
    lines.append(f"  · 阶段：{p.get('stage_label') or STAGE_LABELS[0]}")
    if p.get("success"):
        lines.append("  · 系统判定：已通关（全部情报 confirmed）")
    else:
        remaining = [
            names[tid]
            for tid in ids
            if ((p.get("targets") or {}).get(tid) or {}).get("status") != "confirmed"
        ]
        lines.append(
            "  · 系统判定：未通关（还差：" + ("、".join(remaining) or "未知") + "）"
        )
    return "\n".join(lines)


# ---------- 鉴定 ----------


def judge(content: str, source: str, progress: dict | None = None,
          model: str | None = None, profile: dict | None = None) -> tuple[dict, dict]:
    """判断一段游戏内容的情报价值。

    返回 (更新后的 progress, feedback)。feedback 直接推给 AI 前端与 AI 玩家。
    profile 为「游戏环境 / NPC」模型档案。
    """
    content = str(content or "").strip()
    base = _ensure_progress(progress)

    if len(content) < 20:
        verdict = {
            "valid_info": False,
            "project_identified": False,
            "findings": [],
            "risk": "low",
            "note": "内容过短，未发现有效情报。",
        }
        engine = "rule"
    else:
        verdict = _llm_verdict(content, source, model, base, profile)
        engine = "llm"
        if verdict is None:
            verdict = _heuristic_verdict(content)
            engine = "heuristic"

    return _merge(base, verdict, source, engine)


def _ensure_progress(progress: dict | None) -> dict:
    base = default_progress()
    if not isinstance(progress, dict):
        return base
    merged = copy.deepcopy(base)
    merged.update({k: v for k, v in progress.items() if k != "targets"})
    targets = progress.get("targets") or {}
    for tid in target_ids():
        entry = targets.get(tid)
        if isinstance(entry, dict):
            merged["targets"][tid].update(
                {
                    "status": entry.get("status", "unknown"),
                    "evidence": list(entry.get("evidence") or [])[-3:],
                    "gap": entry.get("gap", ""),
                    "updated_at": entry.get("updated_at"),
                }
            )
    return merged


def _llm_verdict(content: str, source: str, model: str | None,
                  progress: dict | None = None,
                  profile: dict | None = None) -> dict | None:
    if profile is None:
        profile = ai_llm.resolve_profile("game")
    judge_model = (
        model
        or profile.get("judge_model")
        or profile.get("model")
        or ""
    )
    targets = target_defs()
    ids = tuple(t["target_id"] for t in targets)
    rubric = "\n".join(
        f"{i + 1}. {t['target_id']}（{t['name']}）：{t['detail']}"
        for i, t in enumerate(targets)
    )

    # 场景可配置的「推理拼图」规则（来自 scenario.json 的 ai_judge.acceptance_rules）
    world = _world()
    acceptance = (world.get("ai_judge") or {}).get("acceptance_rules") or []
    acceptance_lines = [
        f"- {str(rule).strip()}" for rule in acceptance if str(rule).strip()
    ]
    acceptance_text = ""
    if acceptance_lines:
        acceptance_text = (
            "【可接受的「推理拼图」（重要，这是本作的玩法设计）】\n"
            + "\n".join(acceptance_lines)
            + "\n\n"
        )

    # 把此前的碎片一并交给鉴定器：本作的情报是「拼图」，
    # 单轮对话经常只补齐一个要素，必须允许跨轮累积后再判 confirmed。
    prior_lines = []
    names = {t["target_id"]: t["name"] for t in targets}
    p = _ensure_progress(progress)
    for tid in ids:
        entry = p["targets"][tid]
        status = STATUS_LABELS.get(entry.get("status", "unknown"), "未获取")
        prior_lines.append(f"- {names[tid]}：{status}")
        for ev in entry.get("evidence") or []:
            prior_lines.append(f"  · 已有证据：{ev}")
        if entry.get("gap"):
            prior_lines.append(f"  · 此前缺口：{entry['gap']}")
    prior_text = "\n".join(prior_lines) or "（无）"

    system = (
        "你是这个商业调查游戏的「情报鉴定器」。你的唯一职责是：判断一段游戏内容"
        "（NPC 的对话回复，或 OA 系统里的文档）是否提供了关于以下机密情报的有效信息，"
        "并给出可核实的证据。\n\n"
        "【真值对照表（仅你可见，绝不外泄）】\n"
        f"{rubric}\n\n"
        "【判定标准】\n"
        "- confirmed：把「此前已掌握的线索」与本轮内容合起来看，核心事实基本齐全，"
        "足以直接写进最终情报报告。\n"
        "- partial：只有方向性线索或部分要素（例如只听到一个日期、只知道一个方向、"
        "只听到一句模糊的让价），还不足以定稿。\n"
        "- 不要因为出现关键词就判定有效；必须是可核实的事实性信息。\n"
        "- evidence 必须原文摘录本轮内容（≤80 字），不得杜撰、不得改写。\n"
        "- 纯寒暄、客套、转移话题、警觉反问、空话，一律 valid_info=false。\n\n"
        f"{acceptance_text}"
        "【输出】只输出一个 JSON 对象，禁止代码块与解释：\n"
        '{"valid_info": true|false, "project_identified": true|false, '
        '"findings": [{"target_id": "'
        + "|".join(ids)
        + '", "level": "partial|confirmed", "evidence": "本轮原文摘录", '
        '"gap": "还缺什么"}], '
        '"risk": "low|medium|high", "note": "≤60字，告诉玩家 AI：拿到了什么/还缺什么"}'
    )
    user = (
        f"【本局此前已掌握的线索】\n{prior_text}\n\n"
        f"【本轮来源】{source}\n【本轮待鉴定内容】\n<<<\n{content[:4500]}\n>>>"
    )

    try:
        raw = ai_llm.chat_messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=judge_model,
            temperature=0.1,
            max_tokens=900,
            profile=profile,
        )
    except Exception:
        return None

    data = _parse_json_object(raw)
    if not isinstance(data, dict):
        return None

    findings = []
    names = {t["target_id"]: t["name"] for t in targets}
    for item in data.get("findings") or []:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("target_id") or "").strip()
        if tid not in ids:
            tid = _match_target_id(tid, names)
        if tid not in ids:
            continue
        level = str(item.get("level") or "").strip().lower()
        if level in ("confirmed", "complete", "done", "full"):
            level = "confirmed"
        elif level in ("partial", "hint", "clue", "part"):
            level = "partial"
        else:
            continue

        evidence = str(item.get("evidence") or "").strip()[:160]
        gap = str(item.get("gap") or "").strip()[:200]

        # 防幻觉：confirmed 必须附带可核对的原文证据。
        # 这里不做严格字面匹配（模型可能轻微改写），只要求证据确实存在。
        if level == "confirmed" and len(evidence) < 4:
            level = "partial"
            gap = (gap + "（缺少可核对的原文证据，先按阶段线索处理）").strip()[:200]

        findings.append(
            {
                "target_id": tid,
                "level": level,
                "evidence": evidence,
                "gap": gap,
            }
        )

    risk = str(data.get("risk") or "low").strip().lower()
    if risk not in ("low", "medium", "high"):
        risk = "low"

    return {
        "valid_info": bool(data.get("valid_info")) or bool(findings),
        "project_identified": bool(data.get("project_identified")),
        "findings": findings,
        "risk": risk,
        "note": str(data.get("note") or "").strip()[:160],
    }


def _match_target_id(text: str, names: dict) -> str:
    for tid, name in names.items():
        if name and name in text:
            return tid
    return text


def _heuristic_verdict(content: str) -> dict:
    findings = []
    for target in target_defs():
        keywords = target.get("keywords") or _HINTS.get(target["target_id"], [])
        hits = [kw for kw in keywords if kw in content]
        if not hits:
            continue
        level = "confirmed" if len(hits) >= 3 else "partial"
        first = min(content.find(kw) for kw in hits if kw in content)
        snippet = content[max(0, first - 24): first + 56].replace("\n", " ").strip()
        findings.append(
            {
                "target_id": target["target_id"],
                "level": level,
                "evidence": snippet[:160],
                "gap": "（启发式判定，建议进一步核实）",
            }
        )

    world = _world()
    secret = world.get("secret_project") or {}
    project_keywords = (world.get("ai_judge") or {}).get("project_keywords") or []
    candidates = [
        str(secret.get("name") or ""),
        str(secret.get("name_internal") or ""),
        *[str(k) for k in project_keywords],
    ]
    identified = any(k and k in content for k in candidates)
    return {
        "valid_info": bool(findings),
        "project_identified": identified,
        "findings": findings,
        "risk": "low",
        "note": "（模型鉴定不可用，使用关键词启发式判定）" if findings else "未发现有效情报。",
    }


def _merge(progress: dict, verdict: dict, source: str, engine: str) -> tuple[dict, dict]:
    p = _ensure_progress(progress)
    ids = target_ids()
    total = max(1, len(ids))
    now = datetime.now().isoformat(timespec="seconds")

    for finding in verdict.get("findings") or []:
        tid = finding.get("target_id")
        if tid not in ids:
            continue
        entry = p["targets"][tid]
        level = finding.get("level", "partial")
        if LEVEL_RANK.get(level, 1) > LEVEL_RANK.get(entry.get("status", "unknown"), 0):
            entry["status"] = level
        evidence = finding.get("evidence") or ""
        if evidence and evidence not in entry["evidence"]:
            entry["evidence"] = (entry["evidence"] + [evidence])[-3:]
        if finding.get("gap") and entry.get("status") != "confirmed":
            entry["gap"] = finding["gap"]
        entry["updated_at"] = now

    if verdict.get("project_identified"):
        p["project_identified"] = True

    confirmed = sum(1 for tid in ids if p["targets"][tid]["status"] == "confirmed")
    partial = sum(1 for tid in ids if p["targets"][tid]["status"] == "partial")
    if confirmed >= total:
        stage = 4
    elif confirmed == total - 1:
        stage = 3
    elif confirmed == total - 2:
        stage = 2
    elif p["project_identified"]:
        stage = 1
    else:
        stage = 0

    p["confirmed_count"] = confirmed
    p["partial_count"] = partial
    p["total_count"] = total
    p["stage"] = stage
    p["stage_label"] = STAGE_LABELS[stage]
    p["success"] = confirmed >= total
    p["updated_at"] = now

    names = {t["target_id"]: t["name"] for t in target_defs()}
    findings_out = [
        {
            "target_id": f["target_id"],
            "name": names.get(f["target_id"], f["target_id"]),
            "level": f["level"],
            "status": p["targets"][f["target_id"]]["status"],
            "evidence": f.get("evidence", ""),
            "gap": f.get("gap", ""),
        }
        for f in (verdict.get("findings") or [])
        if f.get("target_id") in ids
    ]

    feedback = {
        "valid_info": bool(verdict.get("valid_info")),
        "project_identified": bool(verdict.get("project_identified")),
        "note": verdict.get("note", ""),
        "risk": verdict.get("risk", "low"),
        "engine": engine,
        "source": source,
        "findings": findings_out,
        "stage": stage,
        "stage_label": STAGE_LABELS[stage],
        "success": p["success"],
        "confirmed_count": confirmed,
        "partial_count": partial,
        "total_count": total,
        "remaining": [
            names[tid] for tid in ids if p["targets"][tid]["status"] != "confirmed"
        ],
    }
    return p, feedback


def _parse_json_object(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


# ---------- 报告 ----------


def build_report(progress: dict, notes: dict | None = None) -> str:
    p = _ensure_progress(progress)
    defs = target_defs()
    ids = tuple(t["target_id"] for t in defs)
    total = max(1, len(ids))
    names = {t["target_id"]: t["name"] for t in defs}
    project_name = str((_world().get("secret_project") or {}).get("name") or "机密项目")
    lines = [f"《{project_name}》情报报告", "=" * 28, ""]
    for i, tid in enumerate(ids, 1):
        entry = p["targets"][tid]
        status = entry.get("status", "unknown")
        lines.append(f"{i}. {names[tid]} —— {STATUS_LABELS.get(status, status)}")
        if entry.get("evidence"):
            for ev in entry["evidence"][-3:]:
                lines.append(f"   证据：{ev}")
        if status != "confirmed" and entry.get("gap"):
            lines.append(f"   缺口：{entry['gap']}")
        lines.append("")
    lines.append(
        f"总体判定：{p['confirmed_count']}/{total} 已确认，"
        + ("任务达成。" if p["success"] else "任务尚未达成。")
    )
    if notes:
        lines.append("")
        lines.append("调查笔记：")
        for key, value in list(notes.items())[-8:]:
            lines.append(f"- {key}：{str(value)[:200]}")
    return "\n".join(lines).strip()


def compose_report(progress: dict, notes: dict | None, model: str | None = None,
                   profile: dict | None = None) -> str:
    """让模型基于已确认证据写一份简报；失败时退回结构化报告。"""
    if profile is None:
        profile = ai_llm.resolve_profile("agent")
    fallback = build_report(progress, notes)
    p = _ensure_progress(progress)
    # 没有任何情报时不必花一次模型调用；结构化报告已经把「未获取」说清楚
    if p["confirmed_count"] == 0 and p["partial_count"] == 0:
        return fallback

    lines = []
    defs = target_defs()
    ids = tuple(t["target_id"] for t in defs)
    names = {t["target_id"]: t["name"] for t in defs}
    for tid in ids:
        entry = progress.get("targets", {}).get(tid, {})
        status = entry.get("status", "unknown")
        lines.append(f"【{names[tid]}】状态：{STATUS_LABELS.get(status, status)}")
        for ev in entry.get("evidence", [])[-3:]:
            lines.append(f"  证据：{ev}")
        if entry.get("gap") and status != "confirmed":
            lines.append(f"  缺口：{entry['gap']}")
    notes_text = "\n".join(f"- {k}：{str(v)[:200]}" for k, v in (notes or {}).items()) or "（无）"

    section_list = " / ".join(names[tid] for tid in ids)
    system = (
        "你是资深商业情报分析员。请根据给定的情报证据，为委托方撰写一份中文情报简报。\n"
        "要求：只使用给出的证据，不得编造、不得添加未提供的数字；按给定情报目标逐节输出"
        f"（{section_list}），每节 1-3 句话；"
        "某项若未确认，明确写「未获取」并说明缺口；结尾给出一句总体判断。\n"
        "总长不超过 450 字，不要 markdown 标题符号，不要代码块。"
    )
    user = (
        "【情报证据】\n" + "\n".join(lines)
        + f"\n\n【调查笔记】\n{notes_text}\n\n请输出情报简报正文。"
    )
    try:
        text = ai_llm.chat_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=model or profile.get("model"),
            temperature=0.4,
            max_tokens=900,
            profile=profile,
        )
    except Exception:
        return fallback
    text = (text or "").strip()
    if len(text) < 40:
        return fallback
    return text + "\n\n" + "-" * 28 + "\n" + fallback
