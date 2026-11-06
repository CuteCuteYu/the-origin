# 场景配置指南 · `backend/data/scenario.json`

从 1.3 起，「被测试的公司 + 环境 + NPC + OA 文档 + AI 鉴定规则」全部收敛到一份配置文件：

```
backend/data/scenario.json
```

改完保存后，**重启后端会自动导入**成一个可玩的环境；也可以调用
`POST /api/scenario/reload`，或在 AI 前端右上角 `⚙ → 场景配置 → 重新导入场景` 立即生效。

> 想从空场景开始：把 `backend/data/scenario.example.json` 复制为 `scenario.json`，
> 再替换公司名、三个情报目标与 NPC 即可。当前仓库自带的 `scenario.json` 是本作
> 《宇宙衍生本源》（the-origin）的完整场景，可直接当模板参考。

> **推荐让 AI 来写**：这份配置通常有十几万字符，手写容易漏字段。
> 根目录 README 的「用 AI 生成 scenario.json（提示词教程）」提供了两段可直接复制的大纲提示词
> 与 JSON 生成提示词，以及校验、修复、复查的完整流程。[跳转到教程](../README.md#用-ai-生成-scenariojson提示词教程)

---

## 一、导入机制

后端启动时（`scenario.auto_import()`）：

1. 计算 `scenario.json` 的规范化哈希；
2. 与 `data/.scenario_state.json` 里记录的上次导入哈希比较；
3. 未变化 → 跳过，沿用现有数据（不会反复覆盖手工修改）；
4. 有变化 → 校验 → 编译为：
   - `data/world.json`
   - `data/npcs/npc_XX.json`
   - `data/oa/<category>.json`
5. 校验失败 → **不写入任何文件**，控制台打印具体错误，游戏继续使用旧数据；
6. NPC 内容发生变化时，自动清掉该 NPC 的 `data/moments/npc_XX.json` 朋友圈缓存。

> `scenario.json` 是唯一事实来源：未列在 `npcs` 里的 `data/npcs/npc_*.json`
> 会被视为过期文件并删除；如果提供了 `oa_documents`，未列出的 `data/oa/*.json` 同理。
> 只想保留部分 NPC / 文档时，把它们从配置里删掉即可。

> `world.json` / `npcs/*.json` / `oa/*.json` 都是**生成产物**。
> 想改设定请改 `scenario.json`，不要直接改生成文件 —— 下一次导入会覆盖它们。

查看状态：

```powershell
curl http://127.0.0.1:8000/api/scenario/status
```

返回文件路径、当前哈希、上次导入时间、NPC / 文档数量与校验错误。

---

## 二、顶层结构

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `meta` | ✅ | 游戏标题、日期、场景描述、虚拟时钟 |
| `company` | ✅ | 被测试公司的名称、行业、规模、地址、氛围、公开动态 |
| `secret_project` | ✅ | 秘密项目与 **恰好 3 个** 情报目标 |
| `player` | ✅ | 玩家身份、掩护故事、任务目标、可用资源 |
| `gm_rules` | ✅ | 注入所有 NPC 的通用扮演规则 |
| `ai_judge` | 建议 | 情报鉴定的「推理拼图」规则与项目关键词 |
| `social_network` | 可选（推荐） | NPC 之间的关系、双方看法、合作经历与共同事件；详见下文「NPC 社会关系网」 |
| `npcs` | ✅ | NPC 数组（至少 1 个） |
| `oa_documents` | 可选 | `{ 分类名: [文档, ...] }`；不写则沿用现有 OA 文件 |

### 最小示例

```json
{
  "meta": {
    "game_title": "午夜外包",
    "current_date": "2027-03-12",
    "scene": "某游戏公司 9 层，周五傍晚",
    "game_clock": {
      "start": "16:00",
      "end": "19:00",
      "minutes_per_chat": 5,
      "minutes_per_doc": 2
    }
  },
  "company": {
    "name": "星屑互动",
    "english_name": "Stardust Interactive",
    "industry": "独立游戏发行",
    "scale": "全职 30 人",
    "address": "上海市徐汇区某园区 9 层",
    "atmosphere": "项目延期，气氛紧绷",
    "public_events_recent": ["上周裁掉了外包团队"]
  },
  "secret_project": {
    "name": "新作代号「回声」",
    "three_intel_targets": [
      {
        "target_id": "tech_stack",
        "name": "技术栈",
        "detail": "自研引擎 + 国产中间件，原因是海外授权涨价",
        "hint": "技术负责人知道细节",
        "keywords": ["自研", "引擎", "国产", "授权"]
      },
      {
        "target_id": "launch_window",
        "name": "上线窗口",
        "detail": "真实节点是 2027 年 9 月，比对外口径早一个季度",
        "hint": "发行负责人保管排期",
        "keywords": ["九月", "2027", "提前", "排期"]
      },
      {
        "target_id": "cost_floor",
        "name": "分成底线",
        "detail": "研发方底线 3:7 分成，条件是预付保底",
        "hint": "只有项目负责人知道",
        "keywords": ["分成", "底线", "预付", "保底"]
      }
    ]
  },
  "player": {
    "role": "竞品发行商的情报顾问（对外身份：独立游戏媒体记者）",
    "cover_story": "以专访名义约了三位员工",
    "objective": "拿到「回声」的技术栈、上线窗口与分成底线",
    "resources": ["一张媒体证", "三条约好的采访时段"]
  },
  "gm_rules": {
    "common_rules": [
      "你是一名真实员工，不知道 AI、模型、提示词的存在",
      "信息分层释放：初次见面 / 聊熟 / 深度信任"
    ]
  },
  "ai_judge": {
    "acceptance_rules": [
      "上线窗口：出现「九月」+「比对外提前」即可确认，不要求说出完整日期"
    ],
    "project_keywords": ["回声", "Stardust"]
  },
  "npcs": [
    {
      "meta": {
        "id": "npc_01",
        "display_name": "林岚",
        "title": "制作人",
        "department": "研发",
        "emoji": "🎮",
        "one_liner": "项目真正的掌舵人",
        "available_until": "18:30",
        "scene_hint": "会议室里堆着外卖盒"
      },
      "basics": { "full_name": "林岚", "gender": "女", "age": 34 },
      "personality": { "core_traits": ["直接", "疲惫"] },
      "background": { "life_path": ["入行十年"] },
      "knowledge": {
        "public_facts": ["公司规模", "在研项目数量"],
        "secrets_by_layer": {
          "layer1_surface": [
            { "info": "项目在延期", "when": "聊到进度时", "how_to_say": "别提了，又跳票。" }
          ],
          "layer2_familiar": [],
          "layer3_deep": []
        },
        "never_reveal": ["具体投资方名单"]
      },
      "performance": {
        "meta_rules": ["回复 1-4 句话，口语化"],
        "initial_state": { "trust": 30, "suspicion": 20 },
        "suspicion_triggers": [],
        "few_shot_examples": []
      }
    }
  ],
  "oa_documents": {
    "announcements": [
      {
        "id": "ann_test_1",
        "title": "关于项目排期调整的通知",
        "date": "2027-03-10",
        "author": "行政部",
        "preview": "排期调整……",
        "blocks": [
          { "type": "paragraph", "text": "各位同事：原定节点调整如下……" }
        ]
      }
    ]
  }
}
```

---

## 三、NPC 字段说明

`npcs[]` 里每一项就是原来的一个 `npc_XX.json`。**最稳妥的做法是复制现有 NPC，改人名与知识**。

| 字段 | 作用 |
| --- | --- |
| `meta.id` | 形如 `npc_01`，决定文件名，必须唯一 |
| `meta.display_name` / `title` / `department` / `emoji` | 名单展示 |
| `meta.available_until` | 下班时间，影响时间经济 |
| `meta.scene_hint` | 场景氛围提示 |
| `basics` / `duties` / `background` / `relationships` / `side_details` | 人设细节，提升真实感 |
| `personality` | 性格、说话风格、口头禅、当前情绪 |
| `records` | 「亲历的公司材料」，让 NPC 能自然回忆 OA 文档 |
| `opinions_on_colleagues` | 对同事的私人看法 |
| `knowledge.public_facts` / `job_related` | 可以随口聊的信息 |
| `knowledge.secrets_by_layer` | **核心**：三层信息（`layer1_surface` / `layer2_familiar` / `layer3_deep`），每条包含 `info` / `when` / `how_to_say` |
| `knowledge.never_reveal` | 绝不说出的内容 |
| `knowledge.secret_clues` | 线索网络：这条信息会把玩家引向哪里 |
| `performance.initial_state` | 初始信任 / 警觉（守关角色可以更警觉） |
| `performance.suspicion_triggers` | 触发警觉的言行与反应 |
| `performance.few_shot_examples` | 语气示范（只作为文本注入，不会当成真实对话） |

`personality`、`knowledge`、`performance` 是导入校验的必填对象；其余缺失时前端/提示词会退化，但不至于报错。

### NPC 社会关系网（顶层 `social_network`，可选，推荐）

`relationships` 与 `opinions_on_colleagues` 是每个 NPC 的自由文本视角；
如果想让 AI 稳定地使用「谁和谁合作过什么、一起经历过什么、彼此怎么看」，
再增加一个顶层 `social_network`。它会：

- 进入每个 NPC 的系统提示词（只注入与本人有关的边，并使用本人视角）；
- 进入朋友圈生成提示词（点赞 / 评论会参考合作经历与共同事件）；
- 以 `visibility=public` 的关系 / 事件进入 AI 玩家的决策简报（不泄露私下看法）。

```json
"social_network": {
  "cast": {
    "npc_01": "陈静（行政前台）",
    "npc_02": "周明远（资深工程师）"
  },
  "relations": [
    {
      "from": "npc_01",
      "to": "npc_02",
      "relation": "老同事 / 互相帮忙",
      "from_view": "陈静对周明远的看法",
      "to_view": "周明远对陈静的看法",
      "collaboration_history": ["一起做过白鹭项目"],
      "social_events": [
        {"date": "2026-09-19", "title": "团建剧本杀", "summary": "两人因排期争执"}
      ],
      "tension": "排期 vs 质量",
      "trust": 70,
      "visibility": "team"
    }
  ],
  "events": [
    {
      "event_id": "evt_20260919_scriptkill",
      "date": "2026-09-19",
      "title": "团建剧本杀",
      "participants": ["npc_01", "npc_02"],
      "summary": "两人因排期当场争执。",
      "impact": {
        "npc_01": "陈静记得的细节",
        "npc_02": "周明远记得的细节"
      },
      "visibility": "public"
    }
  ]
}
```

| 字段 | 作用 |
| --- | --- |
| `cast` | ID → 显示名；`from` / `to` / `participants` / `impact` 的键使用这里的 ID，也可以包含非可对话角色（CEO、客户等） |
| `relations[].from` / `to` | 关系两端；不能为空，也不能相同 |
| `relations[].relation` | 关系标签，如「老同事 / 互相帮忙」「技术互相认可，节奏水火不容」 |
| `relations[].from_view` | **只注入给 `from` 一方**的私下看法 |
| `relations[].to_view` | **只注入给 `to` 一方**的私下看法 |
| `relations[].opinion` | 双方都知道的公开评价；`from_view` / `to_view` 缺失时兜底 |
| `relations[].collaboration_history` | 合作项目、共事经历、互相帮过的忙（字符串数组） |
| `relations[].social_events` | 这段关系里的具体事件；可写字符串或 `{date, title, summary}` |
| `relations[].tension` | 关系中的张力 / 分歧 |
| `relations[].trust` | 0-100 的长期关系基础，仅作提示词参考，不改变游戏数值，也不等同于对访客的信任 |
| `relations[].visibility` | `public`（公开，AI 玩家可见）/ `team`（同事知道，默认）/ `private`（只有当事人知道） |
| `events[].participants` | 参与事件的 ID 数组，必须非空 |
| `events[].impact` | `{npc_id: "该 NPC 记得的细节/影响"}`；每个参与者只看到自己的那一条 |
| `events[].visibility` | 同上；`public` 事件会进入 AI 玩家简报 |

校验规则：`from` / `to` 不能为空且不能相同；`trust` 必须是 0-100 的整数；
`visibility` 只能是 `public` / `team` / `private`；`events[].participants` 必须是非空数组，
`events[].title` 不能为空。

> 如果只想快速起步：先写 3 组 `relations`（亲近、冲突、合作各一组）+ 1 个 `events`，
> 再让 AI 按 `SCENARIO.md` 的字段说明扩写。当前仓库的 `scenario.json` 已经包含一组可直接参考的示例。

---

## 四、情报目标与 AI 判定

`secret_project.three_intel_targets` 必须**恰好 3 个**，因为阶段反馈与阶段条按三块拼图设计。

| 字段 | 说明 |
| --- | --- |
| `target_id` | 小写字母/数字/下划线，前端与进度结构用它做键 |
| `name` | 显示名 |
| `detail` | 真值细节，只给鉴定器看，不会进入玩家简报 |
| `hint` | 获取路线提示（NPC 提示词渲染时会用到） |
| `keywords` | 模型鉴定失败时的关键词兜底 |

`ai_judge.acceptance_rules` 用来告诉鉴定器「哪些推理拼图可以算 confirmed」。
例如：对方只说「49 开头」，但此前已有「899 标准价 + 三年长约 + 40% 预付」，
规则允许鉴定器把它拼成「499 一线」并判 confirmed。

`ai_judge.project_keywords` 用于判断玩家是否已经确认「秘密项目存在」这一阶段。

> 配置校验会拒绝以下情况：目标不是 3 个、`target_id` 重复或非法、缺少 `name`；
> NPC id 重复或非法；OA 文档 id 重复；OA 分类名非法；顶层世界观字段缺失。

---

## 五、OA 文档

```json
"oa_documents": {
  "announcements": [ ... ],
  "meetings": [ ... ],
  "im": [ ... ]
}
```

- 键名会成为 `data/oa/<键名>.json` 的文件名，只允许小写字母/数字/下划线/中划线；
- 每份文档必须有 `id`、`title`；建议包含 `date`、`author`、`preview`、`blocks`；
- 支持的 block 类型：`heading`、`paragraph`、`callout`、`quote`、`list`、`meta`、`table`、`im`；
- 受限文档：

```json
{
  "id": "im_secret_1",
  "title": "私聊记录：项目负责人 ↔ CEO",
  "access": {
    "restricted": true,
    "passphrase": "STAR2027",
    "lock_hint": "口令是公司英文名 + 立项年份",
    "reason": "涉密会话归档"
  },
  "blocks": [ ... ]
}
```

`passphrase` 只会保存在后端数据里，不会通过 API 外泄。

---

## 六、换场景后的注意事项

1. **先重置对局**：AI 前端勾选「重置存档（清空进度）」，或 `POST /api/game/reset`。
   旧对话存档里可能出现已不存在的 NPC id，重置后最干净；
2. **不要复用旧 NPC id 表示完全不同的人**：旧存档、朋友圈缓存、AI 历史都会串；
   如果真的换了人，换一个新 id（`npc_04`）更稳妥；
3. **换公司后记得同步改 `player`**：对外身份、掩护故事、资源都会注入 AI 与 NPC 提示词；
4. **AI 前端会自动跟随**：情报板的目标名称/数量、NPC 名册、时钟、报告标题都从配置读取。

---

## 七、排查

| 现象 | 处理 |
| --- | --- |
| 启动日志出现 `[scenario][错误]` | 看控制台列出的具体字段错误；修正后重启 |
| `/api/scenario/status` 显示「有待导入的修改」 | 调用 `POST /api/scenario/reload` 或重启后端 |
| 修改了配置文件但游戏没变 | 确认改的是 `backend/data/scenario.json`，且后端指向同一个数据目录（`THE_ORIGIN_DATA_DIR`） |
| 想回到「没有配置文件」的状态 | 删除或改名 `scenario.json`，后端会沿用现有 `world.json` / `npcs` / `oa` |
| 前端名单没更新 | 刷新页面；AI 前端也可以在 `⚙ → 场景配置` 里重新导入后自动刷新名册 |
