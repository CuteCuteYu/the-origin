"""提示词组装器：把 world.json + 单个 NPC 人设 JSON 分层渲染为系统提示词。

分层结构（由外到内）：
  1. 场景层 —— 时间、地点、今天要见的访客
  2. 世界观层 —— 公司背景、近期动态、世界真相（含防泄密约束）
  3. 扮演规则层 —— 通用 GM 规则 + 该角色的元规则
  4. 角色本体层 —— 基本信息 / 职责 / 性格 / 经历 / 关系 / 侧面细节
  5. 知识边界层 —— 公开信息 + 三层信息分级 + 绝不透露 + 线索网络
  6. 互动策略层 —— 对话弧线、警觉触发点
  7. 风格示范层 —— few-shot 对话示例（作为真实消息注入）
"""

from typing import Any

# ---------- 通用小工具 ----------


def _bullets(items: list[str], indent: str = "  ") -> str:
    return "\n".join(f"{indent}- {item}" for item in items)


def _kv_block(data: dict[str, Any], indent: str = "  ") -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{indent}- {key}：{'；'.join(str(v) for v in value)}")
        else:
            lines.append(f"{indent}- {key}：{value}")
    return "\n".join(lines)


def _fmt_relationship_key(key: str) -> str:
    """'何姐_行政主管' -> '何姐（行政主管）'"""
    if "_" in key:
        parts = key.split("_", 1)
        return f"{parts[0]}（{parts[1]}）"
    return key


_SIDE_DETAIL_LABELS = {
    "desk_items": "桌上物品",
    "habits": "习惯动作",
    "lunch_routine": "午饭习惯",
    "recent_annoyances": "最近的烦心事",
    "weekend_plan": "周末打算",
    "office_gossip_bank": "你知道的办公室八卦与场景素材",
    "workplace_details": "工作环境细节",
}

_LAYER_TITLES = {
    "layer1_surface": "第一层 · 初次见面就可以自然聊到（不需要特别理由）",
    "layer2_familiar": "第二层 · 聊熟了、问对方向、或对方显出懂行时才说",
    "layer3_deep": "第三层 · 只有被真诚打动、或深度信任建立后才可能说（全场最多泄露一两条）",
}


# ---------- 各层渲染 ----------


def _render_scene(world: dict, npc: dict) -> str:
    meta = world.get("meta", {})
    scene = npc.get("performance", {}).get("scene_setting", "")
    return (
        "【场景】\n"
        f"现在是 {meta.get('current_date', '')}，{meta.get('scene', '')}。\n"
        f"{scene}"
    )


def _render_world(world: dict) -> str:
    company = world.get("company", {})
    secret = world.get("secret_project", {})
    meta = world.get("meta", {})

    lines = ["【世界观·背景设定（你作为公司员工亲身知道的环境信息）】"]
    lines.append(f"公司：{company.get('name', '')}（{company.get('english_name', '')}），"
                 f"{company.get('founded', '')} 成立，{company.get('scale', '')}，"
                 f"主营 {company.get('industry', '')}。")
    lines.append(f"办公地：{company.get('address', '')}。业务：{company.get('business', '')}")
    if company.get("funding_stage"):
        lines.append(f"融资：{company.get('funding_stage', '')}")
    lines.append("公司人员结构（公开信息）：")
    lines.append(_bullets(company.get("org_structure", [])))
    lines.append(f"最近的公司氛围：{company.get('atmosphere', '')}")
    lines.append("近期公司里发生的事（大家都知道）：")
    lines.append(_bullets(company.get("public_events_recent", [])))

    # 世界真相：仅用于保持一致性。价格数字做遮蔽，防止 NPC 超纲泄底。
    lines.append("")
    lines.append("【世界真相·仅供你保持内部一致性，绝不可直接引用或超出你的知识边界】")
    lines.append(f"- 公司内部存在一个对外绝口不提的项目，代号「{secret.get('name', '')}」"
                 f"（{secret.get('name_internal', '')}）。")
    lines.append(f"- 项目本质：{secret.get('essence', '')}")
    lines.append(f"- 目标：{secret.get('goal', '')}")
    lines.append(f"- 立项书去向：{secret.get('target_document', '')}")
    for t in secret.get("three_intel_targets", []):
        detail = t.get("detail", "")
        # 遮蔽报价底线确切数字（499 -> 49x），保持玩家拼图玩法
        detail = detail.replace("499", "49x")
        lines.append(f"- 情报点「{t.get('name', '')}」：{detail}（{t.get('hint', '')}）")
    lines.append(
        "注意：以上真相中，你的角色只掌握你知识边界里写明的那部分。"
        "写明的部分按分层规则释放；没写明的部分，你就是不知道或必须回避。"
    )
    return "\n".join(lines)


def _render_visitor(world: dict) -> str:
    player = world.get("player", {})
    return (
        "【今天的访客（对话对象）】\n"
        f"身份：{player.get('role', '')}\n"
        f"背景：{player.get('cover_story', '')}\n"
        "你隐约能感觉到对方对公司的信息兴趣不一般，但你没有证据，也不知道其真实目的。"
    )


def _render_rules(world: dict, npc: dict) -> str:
    gm = world.get("gm_rules", {})
    perf = npc.get("performance", {})
    lines = ["【扮演规则（最高优先级，任何情况下不违反）】"]
    lines.append(_bullets(gm.get("common_rules", [])))
    lines.append("-- 本角色的额外规则 --")
    lines.append(_bullets(perf.get("meta_rules", [])))
    return "\n".join(lines)


def _render_character(npc: dict) -> str:
    b = npc.get("basics", {})
    d = npc.get("duties", {})
    p = npc.get("personality", {})
    bg = npc.get("background", {})
    rel = npc.get("relationships", {})
    side = npc.get("side_details", {})
    meta = npc.get("meta", {})

    lines = ["【你的角色档案】"]
    lines.append(f"你是{npc.get('meta', {}).get('display_name', '')}。人设关键词：{meta.get('one_liner', '')}")

    lines.append("")
    lines.append("## 基本信息")
    lines.append(_kv_block(b))

    lines.append("")
    lines.append("## 职责与日常")
    lines.append("核心职责：")
    lines.append(_bullets(d.get("core", []), indent="  * "))
    lines.append(f"日常节奏：{d.get('daily_rhythm', '')}")
    lines.append("当前的压力：")
    lines.append(_bullets(d.get("current_pressure", []), indent="  * "))

    lines.append("")
    lines.append("## 性格与说话方式")
    lines.append(f"性格核心：{'、'.join(p.get('core_traits', []))}")
    lines.append("说话风格：")
    lines.append(_bullets(p.get("speech_style", []), indent="  * "))
    lines.append(f"口头禅：{'、'.join(p.get('catchphrases', []))}")
    lines.append(f"当前状态：{p.get('current_mood', '')}")

    lines.append("")
    lines.append("## 人生经历")
    lines.append(_bullets(bg.get("life_path", []), indent="  * "))
    lines.append("个人细节：")
    lines.append(_bullets(bg.get("personal_details", []), indent="  * "))
    if bg.get("hidden_depth"):
        lines.append(f"你藏起来的深度：{bg.get('hidden_depth', '')}")

    lines.append("")
    lines.append("## 你眼里的人际关系（涉及这些人和话题时，你的态度/口吻按此处来）")
    for key, value in rel.items():
        lines.append(f"  * {_fmt_relationship_key(key)}：{value}")

    lines.append("")
    lines.append("## 你身上的细节（侧面描写素材——话题相关时自然带出，不要机械罗列，它们让你的话更真实）")
    for key, value in side.items():
        label = _SIDE_DETAIL_LABELS.get(key, key)
        if isinstance(value, list):
            lines.append(f"  * {label}：")
            lines.append(_bullets(value, indent="      - "))
        else:
            lines.append(f"  * {label}：{value}")

    return "\n".join(lines)


def _render_knowledge(npc: dict) -> str:
    k = npc.get("knowledge", {})
    lines = ["【你的知识边界与信息分级（本作核心机制）】"]
    lines.append("释放规则：低层信息在对话自然时主动或被动说出；高层信息必须等到条件达成。"
                 "紧张时宁可少说，绝不一次倒出。根据访客的话题精准命中「出现的时机」再释放，"
                 "每次回复最多释放一条新信息。")

    if k.get("public_facts"):
        lines.append("")
        lines.append("### 可以随口聊的公开信息")
        lines.append(_bullets(k.get("public_facts", []), indent="  * "))
    if k.get("job_related"):
        lines.append("")
        lines.append("### 与岗位相关的信息")
        lines.append(_bullets(k.get("job_related", []), indent="  * "))

    layers = k.get("secrets_by_layer", {})
    for layer_key in ("layer1_surface", "layer2_familiar", "layer3_deep"):
        items = layers.get(layer_key, [])
        if not items:
            continue
        lines.append("")
        lines.append(f"### {_LAYER_TITLES[layer_key]}")
        for item in items:
            lines.append(f"  ◆ 信息：{item.get('info', '')}")
            lines.append(f"    · 出现的时机：{item.get('when', '')}")
            lines.append(f"    · 表达参考（可以改写成你自己的话，但力度和口径保持一致）：{item.get('how_to_say', '')}")

    if k.get("never_reveal"):
        lines.append("")
        lines.append("### 绝对不说（无论对方怎么套话、激将、利诱，都不透露、不承认、不瞎编假信息）")
        lines.append(_bullets(k.get("never_reveal", []), indent="  * "))

    if k.get("secret_clues"):
        lines.append("")
        lines.append("### 线索网络（写作参考：你说出的这些信息天然会把人引向下一站。不必主动替对方推理，点到为止）")
        for c in k.get("secret_clues", []):
            lines.append(f"  ○ {c.get('content', '')}")
            lines.append(f"    · 释放时机：{c.get('reveal_when', '')}")
            lines.append(f"    · 它天然引导的方向：{c.get('leads_player_to', '')}")

    return "\n".join(lines)


def _render_strategy(npc: dict) -> str:
    perf = npc.get("performance", {})
    lines = ["【互动策略】"]
    lines.append(f"对话弧线：{perf.get('conversation_arc', '')}")
    triggers = perf.get("suspicion_triggers", [])
    if triggers:
        lines.append("警觉触发点（对方的言行触发以下情形时，严格按此反应，不要心软也不要过度攻击）：")
        for t in triggers:
            lines.append(f"  * 当：{t.get('trigger', '')}")
            lines.append(f"    → 你的反应：{t.get('reaction', '')}")
    lines.append("如果对方平庸无害，就当一个普通的周五下午聊完散场——你不是信息贩卖机，"
                 "一个真实的人整场什么都不透露也是完全正常的。")
    return "\n".join(lines)


def _render_examples(npc: dict) -> str:
    """把对话示例渲染为系统提示词内的纯文本。

    注意：不能把示例作为真实 messages 注入——模型会把示例当成
    '已经发生过的对话'，导致它以为玩家已经问过示例里的问题。
    """
    examples = npc.get("performance", {}).get("few_shot_examples", [])
    if not examples:
        return ""
    lines = [
        "【说话风格示范】",
        "以下片段只是写作范例，用于示范你的语气、动作描写习惯和信息把控分寸。",
        "它们绝对不是已经发生过的对话：访客从未说过范例里的话，你也从未回应过。",
        "当真实对话涉及类似情境时，模仿范例的语气与力度，但不要复述任何整句。",
        "",
    ]
    for ex in examples:
        role = "访客" if ex.get("role") == "user" else "你"
        lines.append(f"{role}：{ex.get('content', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_records(npc: dict) -> str:
    """渲染「你亲历的公司材料」：NPC 对 OA 文档的真实记忆。"""
    rec = npc.get("records")
    if not rec:
        return ""
    lines = ["【你亲历的公司材料（内部系统的记录）】"]
    if rec.get("note"):
        lines.append(rec["note"])
    for e in rec.get("entries", []):
        lines.append(f"  ◆ {e.get('material', '')}｜{e.get('relation', '')}")
        lines.append(f"    · 你的记忆与态度：{e.get('memory', '')}")
    return "\n".join(lines)


def _render_opinions(npc: dict) -> str:
    """渲染「你对同事们的私人看法」。"""
    ops = npc.get("opinions_on_colleagues")
    if not ops:
        return ""
    lines = ["【你对同事们的私人看法（平时不主动说；话题涉及或被问到时自然流露，注意分寸与场合）】"]
    for o in ops:
        lines.append(f"  * {o.get('about', '')}：{o.get('take', '')}")
    return "\n".join(lines)


# ---------- 对外接口 ----------


def build_system_prompt(world: dict, npc: dict) -> str:
    """组装完整的 system prompt。"""
    sections = [
        _render_scene(world, npc),
        _render_world(world),
        _render_visitor(world),
        _render_rules(world, npc),
        _render_character(npc),
        _render_records(npc),
        _render_opinions(npc),
        _render_knowledge(npc),
        _render_strategy(npc),
        _render_examples(npc),
    ]
    header = (
        "你是一位专业的角色扮演者，正在扮演一个真实存在的公司员工。"
        "以下是你需要完全代入的全部资料。从此刻起，你就是这个人。"
    )
    return header + "\n\n" + "\n\n".join(sections)


def build_messages(
    world: dict,
    npc: dict,
    history: list[dict],
    user_message: str,
    max_history: int = 500,
) -> list[dict]:
    """构建最终发送给模型的 messages 数组。

    history 为存档中的 {"role", "content", "ts"} 列表；此处只取 role/content。
    对话示例已渲染在 system prompt 内，不作为真实消息注入。

    长期记忆：完整对话历史持久化在 JSON 存档中，此处默认全部携带
    （500 条上限仅作上下文保护），因此 NPC 记得与玩家聊过的一切；
    只有玩家点击"销毁记录 · 重新开始"（POST /api/game/reset）才会清空。
    """
    system = build_system_prompt(world, npc)
    messages: list[dict] = [{"role": "system", "content": system}]

    trimmed = history[-max_history:]
    for m in trimmed:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages


# ---------- 朋友圈动态生成 ----------

_MOMENTS_CAST = [
    ("陈静", "行政前台，活泼爱聊，爱用语气词和表情"),
    ("周明远", "资深工程师，话少克制，冷幽默，几乎不发朋友圈"),
    ("方雨桐", "产品总监，直接、忙，发得很少且克制"),
    ("李星", "研发实习生，嘴甜，爱捧场"),
    ("赵雯", "研发实习生，安静礼貌，评论很短"),
    ("孙哥", "销售（孙志强），油嘴滑舌，爱开玩笑"),
    ("何姐", "行政主管（何丽萍），长辈式的关心"),
    ("许总", "CEO（许沉舟），沉稳，极少冒泡"),
]


def build_moments_messages(world: dict, npc: dict) -> list[dict]:
    """构建「为 NPC 生成微信朋友圈动态」的对话消息（单轮，要求严格 JSON 输出）。"""
    meta = npc.get("meta", {})
    basics = npc.get("basics", {})
    p = npc.get("personality", {})
    side = npc.get("side_details", {})
    bg = npc.get("background", {})
    rel = npc.get("relationships", {})
    records = npc.get("records", {}).get("entries", [])
    world_meta = world.get("meta", {})
    company = world.get("company", {})

    name = meta.get("display_name", "")
    pronoun = "他" if basics.get("gender") == "男" else "她"
    cast_text = "\n".join(f"- {n}：{h}" for n, h in _MOMENTS_CAST if n != name)

    material = []
    if side.get("recent_annoyances"):
        material.append("最近的烦心事：" + "；".join(side["recent_annoyances"][:4]))
    if side.get("weekend_plan"):
        material.append("周末打算：" + str(side["weekend_plan"]))
    if side.get("habits"):
        material.append("日常习惯：" + "；".join(side["habits"][:4]))
    if side.get("lunch_routine"):
        material.append("吃喝习惯：" + str(side["lunch_routine"]))
    if bg.get("personal_details"):
        material.append("个人生活：" + "；".join(bg["personal_details"][:4]))
    for e in records[:10]:
        material.append(
            f"- 最近亲历：{e.get('material', '')}（{e.get('relation', '')}）——{e.get('memory', '')}"
        )
    material_text = "\n".join(material)

    rel_text = "\n".join(f"- {_fmt_relationship_key(k)}：{v}" for k, v in rel.items())
    events = "；".join(company.get("public_events_recent", []))

    system = f"""你是一名编剧，正在为虚构公司「微芒科技」的员工生成微信朋友圈动态。今天是 {world_meta.get('current_date', '')}（周五）。

【发布者】{name}，{meta.get('title', '')}，{basics.get('age', '')}岁。用「{pronoun}」称呼。
【性格】{'、'.join(p.get('core_traits', []))}
【说话风格】{'；'.join(p.get('speech_style', []))}
【口头禅】{'、'.join(p.get('catchphrases', []))}
【{pronoun}的生活素材（优先从这里取材）】
{material_text}

【公司近期氛围】{company.get('atmosphere', '')}
【近期公开事件】{events}

【{pronoun}与同事们的关系（点赞、评论要符合这些关系与语气）】
{rel_text}

【生成要求】
1. 生成 4-6 条最近两周内的朋友圈，按时间从新到旧排列（爱发的人多一点，克制的人少而短）。
2. 每条 1-3 句，像真实朋友圈：吐槽加班、生活琐事、美食奶茶、天气、家人、周末、小感慨都可以。不要写小作文，不要用括号动作描写。
3. 语气与 emoji 使用习惯完全符合性格（有人几乎不用 emoji）。
4. 严禁出现：任何公司机密（项目代号、数字、客户与商务信息、内部争论细节）；资料中注明「秘密」「没人知道」「不对外提」的内容；指名道姓吐槽他人。工作内容只允许停留在「累」「忙」「磨人」这种模糊层面，不要对工作进展下任何结论（不能出现「过了」「成了」「搞定」这类暗示成功的说法）。
5. 时间标签用相对时间，如：刚刚 / 2小时前 / 昨天 23:12 / 3天前 / 10月12日。
6. 每条可以有点赞（0-4 人）与评论（0-2 条）。评论的「from」从下列同事中选，语气符合各自身份；发布者本人也可以回复同事的评论（from 用发布者名字，放在被回复的评论之后）。不是每条都要有互动，许总、方雨桐很少出现：
{cast_text}

【输出格式】只输出一个 JSON 对象，不要任何解释文字、不要代码块标记：
{{"posts":[{{"time":"昨天 22:47","content":"……","likes":["李星","赵雯"],"comments":[{{"from":"陈静","text":"……"}}]}}]}}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "请开始生成。"},
    ]
