# 宇宙衍生本源 · the-origin

> **《微芒之下 · 商业调查档案》** —— 一个「AI NPC 社交工程」对话游戏 · 基础课第四课教学项目
>
> 你扮演一名商业调查员，用一场场对话，从一家公司员工的嘴里套出秘密项目的情报。

---

## 目录

- [游戏简介](#游戏简介)
- [玩法与目标](#玩法与目标)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [界面与功能](#界面与功能)
- [项目架构](#项目架构)
- [核心设计](#核心设计)
  - [① NPC 人设系统](#1-npc-人设系统)
  - [② 信息三层分级机制](#2-信息三层分级机制)
  - [③ 提示词分层组装](#3-提示词分层组装)
  - [④ OA 文档系统](#4-oa-文档系统)
  - [⑤ 记忆系统](#5-记忆系统)
- [API 参考](#api-参考)
- [数据文件格式](#数据文件格式)
- [自定义指南](#自定义指南)
- [开发笔记（踩坑记录）](#开发笔记踩坑记录)
- [常见问题](#常见问题)
- [教学使用建议](#教学使用建议)

---

## 游戏简介

《微芒之下》是一个由大语言模型实时驱动的文字对话游戏。

- **场景**：深圳市南山区智园大厦 14 楼，微芒科技（VigaNex）——一家 48 人的工业级边缘 AI 视觉模组公司；
- **你**：竞争对手派出的情报分析员，对外身份是「睿析咨询」的高级顾问，今天是你第三次到访公司；
- **NPC**：三名由 **glm-5.3** 实时扮演的公司员工，拥有完整人设档案、长期记忆与警觉机制；
- **目标**：套出秘密项目「启明计划」的三块情报拼图（技术路线 / 量产时间表 / 报价底线）；
- **特色**：公司还挂着一套模拟 OA 系统，里面藏着 18 份从人设推导出的内部文档——公告、会议纪要、周报、群聊归档、项目复盘。**先侦查，再开口。**

> 系统不会判定胜负。什么时候算「拿到手」，由你自己判断。

---

## 玩法与目标

### 三块情报拼图

| 情报 | 内容（剧透警告） | 获取路线 |
| --- | --- | --- |
| **技术路线** | 自研轻量多模态模型 + 国产 NPU 路线的真相：2026 年 2 月与海外 IP 公司的授权谈判破裂，CEO 拍板全自研 | 周明远（layer3） |
| **量产时间表** | 真实节点：2027-03 小批量试产（PVT）、2027-05 量产（MP）——比对外口径「2027 年下半年」早一个季度 | 方雨桐（layer3）+ 陈静「三月」碎片 |
| **报价底线** | 标准报价 899 元；对头部客户首年可大幅让价（49 开头）、条件是「三年长约 + 40% 预付」；且「这个数字不落任何文件」 | 方雨桐（layer3）+ 陈静「不能上文件的数字」碎片 |

### 游戏机制

- **无系统胜负判定**：左侧「情报拼图」勾选框是你自己的笔记，勾不勾、算不算拿到，全凭自己判断；
- **信息三层分级**：每个 NPC 的信息分为「初次见面即可聊到 / 聊熟问对方向才说 / 深度信任才可能说」三层，同一句话在不同信任度下的回应完全不同；
- **来源警觉**：如果外部顾问说出只有内部才有的细节，NPC 会立刻追问「你从哪知道的」——引用 OA 材料是双刃剑，方式得当是敲门砖，方式鲁莽是催命符；
- **长期记忆**：NPC 记得你之前说过的每一句话（包括你随口报的名字），只有「销毁记录」才会失忆。

### 推荐游玩路线

1. **先逛 OA 系统**：读周报、纪要、群聊，记下每个人在乎什么、介意什么；
2. **与陈静（16:00 · 前台）聊**：她是八卦枢纽，能拿到「启明」代号、剧本杀事件、「那个数字」等钩子，并告诉你该去找谁；
3. **攻周明远（17:00 · 会议室 B）**：用技术共鸣（产线、散热、标定）打开他的话匣子，深挖「历史原因」；
4. **最后见方雨桐（18:00 · 会议室 A）**：她是守关 BOSS，需要你带着从其他两人处获得的真实碎片，通过她的「诚实度测试」与「你要拿它做什么」的评估。

---

## 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | React 18 + Vite 5 | 双视图：访谈室（聊天）+ OA 模拟系统 |
| 后端 | Python 3.10+ / FastAPI + uvicorn | 8 个接口，全部逻辑集中在 5 个 Python 文件 |
| 环境管理 | uv | `uv sync` / `uv run` |
| 存储 | 本地 JSON 文件 | 无数据库；人设、世界观、OA 文档、对话存档全部是 JSON |
| 模型 | glm-5.3（OpenAI 兼容接口） | 自动扫描系统 `OPENAI*` 环境变量 |

---

## 快速开始

### 一键启动（推荐）

在项目根目录（`code\`）用 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

也可以直接右键 `start.ps1` →「使用 PowerShell 运行」。

脚本会自动完成：**环境检查**（uv / npm / API Key）→ 启动**后端窗口**（:8000）→ 启动**前端窗口**（:5173）→ 打开浏览器。首次运行若缺少依赖会自动安装（`npm install` / `uv sync`）。

> `start.ps1` 内容为**纯 ASCII 英文**（无任何中文字符），因此不受控制台代码页与编码设置影响，不会出现中文乱码；脚本通过 `$PSScriptRoot` 自动定位项目路径，项目目录含中文也完全兼容。

停止服务：关闭它打开的两个服务窗口（或在各窗口内按 Ctrl+C）。若提示「禁止运行脚本」，见文末常见问题 Q8。

### 环境要求

- Python 3.10+ 与 [uv](https://docs.astral.sh/uv/)
- Node.js 18+
- 一个 OpenAI 兼容的模型 API Key（默认适配智谱 BigModel 端点）

### 1. 配置模型密钥（只需一次）

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "你的key", "User")
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4", "User")
# 设置后重启终端 / VSCode 生效
```

后端启动时会自动扫描全部 `OPENAI*` 前缀的环境变量，并打印变量名与掩码值（值不会泄漏到日志）：

```
[config] 扫描系统环境变量中的 OPENAI* 配置：
  发现 OPENAI_API_KEY = e919b***ffKQ
  发现 OPENAI_BASE_URL = https***s/v4
[config] 使用模型: glm-5.3
```

### 2. 启动后端（端口 8000）

```powershell
cd backend
uv sync                                    # 首次安装依赖
uv run python -m uvicorn main:app --port 8000
```

> 注意：请使用 `uv run python -m uvicorn` 而不是直接运行 `uvicorn`（部分系统上全局安装的 uvicorn 启动器会指向失效的解释器）。

### 3. 启动前端（端口 5173）

```powershell
cd frontend
npm install                                # 首次安装依赖
npm run dev
```

浏览器打开 **http://localhost:5173** 即可开始游戏。

（`vite.config.js` 已配置 `/api` 代理到 `http://127.0.0.1:8000`，前后端无需额外联调配置。）

### 4. 停止服务

在两个终端分别按 `Ctrl + C` 即可；若使用 `start.ps1` 启动的，直接关闭它打开的两个服务窗口即可。

---

## 界面与功能

> 整体视觉采用**微信配色**：深色灰阶基底（#111111 / #191919 / #2C2C2C）、微信绿主色（#07C160）、微信风格绿色聊天气泡（#3EB575）、微信红（#FA5151）用于「机密」与警示；三名 NPC 分别使用微信橙 / 蓝 / 黄作为识别色。

### 访谈室（默认视图）

- 与 NPC 的实时对话；`Enter` 发送，`Shift + Enter` 换行；
- NPC 回复中的（动作/神态描写）以斜体渲染，表演感更强；
- 等待回复时有打字指示器（每个 NPC 有专属文案，如「方雨桐正在评估你的问题……」）；
- 首条对话前提供三句通用开场白，也可直接输入。

### OA 模拟系统（VigaOA）

- 顶部标签切换进入；窗口栏、保密标签、「内部资料」水印齐备；
- **5 大分类、18 份文档**：公告通知 ×3、会议纪要 ×3、日志与周报 ×4、通讯记录 ×5、项目档案 ×3；
- **未读红点计数**（localStorage 持久化）、**搜索**（标题/作者/标签）、面包屑导航。

### NPC 朋友圈（AI 生成）

- 左侧「访谈名单」卡片右上角点击「朋友圈」进入（微信朋友圈风格界面：封面、头像、动态流）；
- 动态由 AI 依据人设**现场生成**：吐槽加班、美食奶茶、家人与周末、小感慨，以及同事们的点赞与评论（评论者与语气严格符合人物关系）；
- 首次打开需 10~30 秒生成，之后缓存到 `backend/data/moments/`，再次进入秒开；支持「刷新动态」重新生成；
- 点击「销毁记录 · 重新开始」会连同朋友圈缓存一起清空，下次进入重新生成。

### 左侧任务简报（常驻）

- 背景掩护与行动目标；「随身资源」可折叠；
- **情报拼图自评勾选框**（localStorage 持久化，勾满三块会出现「该收网了」提示）；
- **访谈名单**：显示每位 NPC 的时段与「已记录 N 问」，点击任意人物自动切回访谈室。

### 顶部操作

- 「销毁记录 · 重新开始」：二次确认后清空**全部 AI 记忆**（对话存档、朋友圈缓存、已读状态、拼图勾选），游戏回到初始状态。

---

## 项目架构

### 目录结构

```
code/
├── README.md                      # 本文档
├── start.ps1                      # 一键启动脚本（纯 ASCII 英文，避免乱码）
├── backend/
│   ├── pyproject.toml             # uv 项目配置（fastapi / uvicorn / openai）
│   ├── main.py                    # FastAPI 入口：8 个路由 + CORS
│   ├── config.py                  # 启动时扫描 OPENAI* 环境变量（掩码打印）
│   ├── llm.py                     # OpenAI 兼容客户端封装（glm-5.3，关闭 thinking）
│   ├── prompt_builder.py          # ★ 提示词组装器：人设 JSON → 10 层 system prompt
│   ├── storage.py                 # JSON 原子读写（world / npcs / oa / saves）
│   └── data/
│       ├── world.json             # 世界观：公司设定、秘密项目真相、GM 规则
│       ├── npcs/
│       │   ├── npc_01.json        # 陈静 · 行政前台（八卦枢纽）
│       │   ├── npc_02.json        # 周明远 · 资深工程师（技术核心）
│       │   └── npc_03.json        # 方雨桐 · 产品总监（守关 BOSS）
│       ├── oa/                    # OA 模拟系统文档（人设衍生物料）
│       │   ├── announcements.json # 公告通知（3 份）
│       │   ├── meetings.json      # 会议纪要（3 份）
│       │   ├── logs.json          # 日志与周报（4 份）
│       │   ├── im.json            # 群聊 / 私聊归档（5 份）
│       │   └── projects.json      # 项目复盘与商务档案（3 份）
│       ├── saves/                 # 运行时生成：每个 NPC 一个对话存档
│       └── moments/               # 运行时生成：朋友圈动态缓存（AI 生成）
└── frontend/
    ├── package.json / vite.config.js / index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                # 状态与数据流（双视图切换、朋友圈弹窗、记忆重置）
        ├── api.js                 # 后端接口封装
        ├── styles.css             # 微信配色主题（深色）+ OA 办公系统 + 朋友圈样式
        └── components/
            ├── BriefingPanel.jsx  # 任务简报 + 情报拼图
            ├── NPCList.jsx        # 访谈名单（含朋友圈入口）
            ├── ChatWindow.jsx     # 聊天窗口（消息渲染 / 打字指示 / 开场白）
            ├── OAWindow.jsx       # OA 系统（分类 / 搜索 / 已读追踪）
            ├── OABlocks.jsx       # OA 文档内容块渲染器（8 种 block 类型）
            └── MomentsModal.jsx   # 朋友圈弹窗（AI 生成动态 / 点赞 / 评论）
```

### 一次对话的完整数据流

```
玩家输入
  → POST /api/npcs/{id}/chat
  → 后端读取 world.json + npc_XX.json + 该 NPC 的完整历史存档（saves/）
  → prompt_builder 组装 ~1.3 万字符的分层 system prompt
  → 调用 glm-5.3（关闭 thinking 模式）
  → 回复与提问一起追加写入 saves/{id}.json（持久化 = 记忆）
  → 返回前端渲染
```

---

## 核心设计

### 1. NPC 人设系统

每个 NPC 是一份约 400 行的 JSON，共 **11 个大节**：

| 大节 | 内容 | 作用 |
| --- | --- | --- |
| `meta` | 展示信息（姓名/职位/emoji/时段/场景提示） | 前端名单 + 会话开场 |
| `basics` | 工号、司龄、籍贯、家庭、居住、薪资感受 | 角色真实性的地基 |
| `duties` | 职责清单、日常节奏、当前压力 | 让 NPC 有「岗位逻辑」 |
| `personality` | 性格标签、说话风格、口头禅、当前情绪 | 语言风格与状态波动 |
| `background` | 成长经历、人生大事、隐藏深度 | 价值观与软肋的来源 |
| `relationships` | 对每个同事的态度与关系史 | 人物关系网 |
| `side_details` | 桌上物品、习惯动作、午饭、烦心事、周末计划、办公室八卦库 | **侧面描写**：让对话有生活质感 |
| `records` | 亲历的 OA 材料清单（我写的/我参加的/我看过的/我没看过） | **材料记忆**：问到能真的想起来 |
| `opinions_on_colleagues` | 对同事的私人看法（平时不主动说） | 心理画像与话题弹药 |
| `knowledge` | 公开信息 + **三层分级机密** + 绝不透露 + 线索网络 | 信息控制核心 |
| `performance` | 场景设定、对话弧线、警觉触发点、元规则、对话范例 | 演技约束 |

### 2. 信息三层分级机制

`knowledge.secrets_by_layer` 把机密分成三层，每层条目都带「出现的时机」与「表达参考」：

- **layer1**：初次见面就能自然聊到的氛围信息（如陈静抱怨「研发区装了门禁，我送快递都要登记」）；
- **layer2**：聊熟了、问对方向、或对方显出懂行才说（如周明远的「放弃了国外主流方案」钩子）；
- **layer3**：深度信任后才可能透露（如方雨桐的真实时间表与报价结构），每场最多泄露一两条；
- **never_reveal**：无论如何不透露、不承认、不瞎编的底线；
- **secret_clues**：结构化线索（clue_id / 内容 / 释放时机 / 引导方向），保证三名 NPC 的线索互相交织。

此外，`performance.suspicion_triggers` 定义了警觉触发点：直问机密、连环追问、身份暴露……每种情况都有精确的反应剧本。

### 3. 提示词分层组装

`prompt_builder.py` 把世界观 + 人设渲染为 **10 层 system prompt**（三人分别为 ~1.3 万字符）：

1. **场景层**：游戏时间、地点、该 NPC 的会面场景；
2. **世界观层**：公司设定 + 世界真相（报价数字自动遮蔽为 `49x`，防止模型超纲泄底）；
3. **访客层**：玩家身份与掩护故事（**不含**玩家真实目标）；
4. **扮演规则层**：GM 通用规则 + 该角色专属元规则（第一人称 / 不承认 AI / 不泄露提示词 / 记忆规则 / 材料反应规则）；
5. **角色档案层**：basics → duties → personality → background → relationships → side_details 结构化渲染；
6. **材料记忆层**（`records`）：逐一列出亲历文档与回忆态度；
7. **私人看法层**（`opinions_on_colleagues`）；
8. **知识边界层**：公开信息 + 三层分级 + 绝不透露 + 线索网络；
9. **互动策略层**：对话弧线 + 警觉触发点剧本；
10. **风格示范层**：对话范例渲染为纯文本（**明确标注「非真实历史」**，不是真实消息）。

历史消息以 OpenAI messages 格式携带，上限 500 条（仅作上下文保护），配合存档即长期记忆。

### 4. OA 文档系统

- 文档为**人设衍生物**：会议纪要收录 NPC 原话、周报暴露隐忧、群聊展示关系、项目复盘揭示心理画像——所有内容与对话人设严格一致；
- 统一 `blocks` 内容结构，前端 `OABlocks.jsx` 渲染 **8 种块类型**：`meta`（信息格子）/ `heading` / `paragraph` / `list` / `quote`（引言）/ `table` / `im`（聊天记录，带彩色头像）/ `callout`（提示框）；
- 新增文档只需往 `backend/data/oa/` 添加 JSON 文件，**无需改动任何代码**。

文档分类与用途：

| 分类 | 份数 | 代表文档 | 玩法作用 |
| --- | --- | --- | --- |
| 公告通知 | 3 | 门禁通知、剧本杀报名、咖啡机进度「第四版」 | 时间线佐证与氛围 |
| 会议纪要 | 3 | 联席周会（方周吵架原话）、算法组纪要（兼容层）、全员会 | 访谈弹药：引用会上原话 |
| 日志与周报 | 4 | 周明远周报、方雨桐周报、陈静日报、李星实习日志 | 心理画像核心载体 |
| 通讯记录 | 5 | 方雨桐↔周明远、陈静↔方雨桐、陈静↔周明远、陈静↔孙志强、算法小组群 | 关系与信息来源 |
| 项目档案 | 3 | 白鹭复盘（「方周模式」）、团建复盘（官方体面版）、张总接待记录 | 人物合作史与性格成因 |

### 5. 记忆系统

- **对话记忆**：完整历史持久化在 `data/saves/{npc_id}.json`（本地文件，重启服务不丢），每次请求全部携带——NPC 记得你说过的每一句话；
- **材料记忆**：人设 `records` 章节让 NPC 对 OA 材料具有真实回忆，并对「外部顾问为何知道内部细节」做来源警觉；
- **重置**：只有点击「销毁记录 · 重新开始」（`POST /api/game/reset`）才删除全部存档与朋友圈缓存，让 NPC 失忆；同时清空 OA 已读状态与拼图勾选。

---

## API 参考

| 方法 | 路径 | 说明 | 返回示例 |
| --- | --- | --- | --- |
| GET | `/api/game/briefing` | 任务简报（公开信息 + 情报拼图名称） | `{ meta, company, player, intel_targets }` |
| POST | `/api/game/reset` | 清空全部对话存档与朋友圈缓存 | `{ ok: true, removed_files: 5 }` |
| GET | `/api/npcs` | NPC 名单（仅展示层信息，绝不泄露人设） | `{ npcs: [{ id, display_name, title, ... }] }` |
| GET | `/api/npcs/{id}/history` | 某 NPC 的完整对话历史 | `{ npc_id, messages: [{ role, content, ts }] }` |
| POST | `/api/npcs/{id}/chat` | 发一句话，返回 NPC 回复 | `{ npc_id, reply }` |
| GET | `/api/oa/documents` | OA 系统全部文档（含 blocks 内容） | `{ documents: [ ... ] }` |
| GET | `/api/npcs/{id}/moments` | 朋友圈动态（无缓存时现场 AI 生成并缓存） | `{ npc_id, generated_at, posts: [...] }` |
| POST | `/api/npcs/{id}/moments/refresh` | 重新生成朋友圈动态（覆盖缓存） | 同上 |

调试示例（PowerShell）：

```powershell
# 列出 NPC
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/npcs" | ConvertTo-Json -Depth 5

# 与陈静对话
$body = @{ message = "陈静你好，今天想聊几句。" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/npcs/npc_01/chat" -Method Post -Body $body -ContentType "application/json"
```

---

## 数据文件格式

### world.json（世界观）

```jsonc
{
  "meta":     { "game_title": "微芒之下", "current_date": "2026-10-16", "scene": "..." },
  "company":  { "name": "微芒科技（深圳）有限公司", "org_structure": ["CEO 许沉舟：...", "..."] },
  "secret_project": {
    "name": "启明计划",
    "three_intel_targets": [
      { "target_id": "tech_route", "name": "技术路线", "detail": "...", "hint": "..." }
    ]
  },
  "player":   { "role": "...", "cover_story": "...", "objective": "...", "resources": ["..."] },
  "gm_rules": { "common_rules": ["..."], "win_condition": "无系统判定..." }
}
```

### npc_XX.json（人设，节选）

```jsonc
{
  "meta": { "id": "npc_01", "display_name": "陈静", "title": "行政前台", "emoji": "🌸" },
  "records": {
    "entries": [
      { "material": "工作日报（10/14）", "relation": "我写的",
        "memory": "快递 63 件、加班统计表初稿、咖啡机第 4 次催办……" }
    ]
  },
  "knowledge": {
    "secrets_by_layer": {
      "layer1_surface": [
        { "info": "研发区 8 月中旬开始装了门禁",
          "when": "聊到公司近况、快递、加班等话题时",
          "how_to_say": "自然地抱怨：'你不知道，八月开始研发那边门禁了……'" }
      ]
    }
  }
}
```

### OA 文档（节选）

```jsonc
{
  "id": "mt_spm_20261013",
  "category": "meetings",
  "title": "产品—研发联席周会纪要（第 14 次）",
  "date": "2026-10-13",
  "author": "产品部 · 方雨桐（审定）",
  "tags": ["周会", "项目"],
  "preview": "整体进度、关键路径与争议事项……",
  "blocks": [
    { "type": "meta", "items": [["时间", "2026-10-13（周二）10:00 - 11:35"], ["地点", "会议室 B"]] },
    { "type": "quote", "text": "我不管工程复杂度，我只要节点。", "source": "——方雨桐" },
    { "type": "callout", "tone": "warn", "text": "本纪要含未公开项目信息，严禁转发。" }
  ]
}
```

---

## 自定义指南

### 修改人设（最常用）

直接编辑 `backend/data/npcs/npc_XX.json`：

- 改性格 → `personality.speech_style` / `catchphrases`；
- 改说话风格 → `performance.few_shot_examples`（风格示范，注意它们**不是**真实对话）；
- 调信息释放时机 → `knowledge.secrets_by_layer` 各条目的 `when` / `how_to_say`；
- 新增材料记忆 → `records.entries`。

后端以 `--reload` 运行时会自动重载，改完即生效（正在进行的对话不受影响）。改完请自行核对 JSON 合法性：

```powershell
uv run python -c "import json;json.load(open('data/npcs/npc_01.json',encoding='utf-8'));print('OK')"
```

### 新增 OA 文档

1. 在 `backend/data/oa/` 对应分类文件中追加一个文档对象（参考上文格式）；
2. 如果希望 NPC「记得」它，把条目写进相关 NPC 的 `records.entries`；
3. 刷新页面即可看到。已读状态按文档 `id` 记录，切勿重复。

### 新增第四名 NPC

1. 复制 `npc_01.json` 为 `npc_04.json`，重写全部内容（保持 11 大节结构）；
2. 世界观中补充该人物在公司结构里的位置（`world.json -> company.org_structure`）；
3. 若涉及新线索，在其余 NPC 的 `relationships` / `records` 中同步提及（保持一致性）；
4. 无需改任何代码——后端按 `npc_*.json` 自动发现，前端自动出现在名单中。

### 调整模型与参数

- 换模型：改 `backend/config.py` 的 `MODEL_NAME`；
- 调整回复风格：改 `backend/llm.py`（temperature 默认 `0.85`；max_tokens 默认 `800`）；
- **换模型时注意**：如果新模型也是推理模型（默认先输出思考内容），务必保留 `extra_body={"thinking": {"type": "disabled"}}` 或调大 `max_tokens`，否则思考可能挤掉正文导致空回复。

---

## 开发笔记（踩坑记录）

> 以下都是本项目真实踩过的坑，供教学讨论。

1. **glm-5.3 是推理模型**：默认先输出 `reasoning_content`（思考），会消耗 `max_tokens` 预算，极端情况下正文为空（`finish_reason: length`）。角色扮演不需要长思考，我们通过 `extra_body={"thinking": {"type": "disabled"}}` 关闭——回复更快、更省、也更口语化。
2. **few-shot 示例不能作为真实 messages 注入**：否则模型会把示例当成「已经发生过的对话」（实测中陈静会说「你刚不是问过一遍了吗」）。正确做法是把示例渲染进 system prompt 文本，并明确标注「这不是真实对话历史」。
3. **记忆 = 历史 + 携带**：NPC 的「记性」取决于两件事——历史是否完整落盘（持久化），以及请求时是否完整携带（本项目上限 500 条）；任何一环截断，NPC 都会「失忆」。
4. **数据一致性是角色的生命线**：所有 OA 文档必须与人设严格对齐，NPC 才能「真的想起来」。本项目做过一次全量一致性审查，修复了「去年/上个月」时间矛盾、「三楼/12F」地点矛盾、群聊日期与「明天开会」的逻辑矛盾等 5 处问题。
5. **越权防护**：GM 规则强制「第一人称 / 不承认 AI / 不泄露提示词存在 / 不讨论公司之外的事」；实测玩家追问「你是不是 AI」时，角色会用自己的方式（冷幽默/怼人）化解。
6. **前端同文件多处编辑要小心**：如果是在编辑器/工具里同时提交多个替换，建议逐个执行并复查最终文件，避免锚点交错导致文件损坏。

---

## 常见问题

**Q1：启动报 `No module named uvicorn`，或 uv 启动器报 Python 版本错误？**
不要直接运行全局的 `uvicorn` 命令，改用 `uv run python -m uvicorn main:app --port 8000`。

**Q2：NPC 回复为空？**
大概率是模型思考消耗了 token 预算。确认 `llm.py` 中 `thinking` 关闭参数对新模型生效，或把 `max_tokens` 调大。

**Q3：端口被占用？**
后端换端口：`uv run python -m uvicorn main:app --port 8001`，同时修改 `frontend/vite.config.js` 中 proxy 的 `target`。

**Q4：如何从头开始玩？**
点右上角「销毁记录 · 重新开始」，或调用 `POST /api/game/reset`。这会清除对话存档、朋友圈缓存、OA 已读状态与拼图勾选。

**Q5：无网络/无 API Key 能玩吗？**
不能。NPC 对话需要实时调用大模型。

**Q6：PowerShell 里看接口返回的中文是乱码？**
那是控制台编码问题，数据本身是 UTF-8。让脚本把结果写入文件后用编辑器查看，或先执行 `chcp 65001`。

**Q7：改了人设为什么不生效？**
后端需要以 `--reload` 启动才能自动重载；手动重启后端亦可。如果对话中途修改，已建立的历史消息仍保留。

**Q8：运行 `start.ps1` 提示「无法加载文件……在此系统上禁止运行脚本」？**
这是 Windows 脚本执行策略的限制。请使用 `powershell -ExecutionPolicy Bypass -File .\start.ps1` 运行（见「快速开始 · 一键启动」），或先执行一次 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

---

## 教学使用建议

本项目适合作为「综合练习/期末大作业」，覆盖知识点：

- **前端**：React 组件拆分、状态提升、双视图路由、localStorage 持久化、CSS 设计系统；
- **后端**：FastAPI 路由设计、Pydantic 校验、CORS、分层模块（config / storage / llm / prompt_builder）；
- **工程化**：uv 环境管理、前后端代理联调、JSON 数据驱动、原子写文件；
- **提示词工程**（本课重点）：角色扮演的人设结构、信息分层控制、防越权规则、few-shot 的正确注入位置、长期记忆设计。

**可布置的改造作业**：

1. 设计第 4 名 NPC（部门自选），并让他的线索与现有三人交织；
2. 为 OA 系统增加「一键引用到对话」按钮（把文档摘要贴进聊天输入框）；
3. 把 JSON 存储替换为 SQLite，并保持接口签名不变；
4. 给 NPC 增加「信任度」可视化系统（后端要求模型输出结构化信任分）；
5. 增加一个「来电」事件：对话中途 NPC 接电话，短暂离线后带回新信息。

---

> 微芒之下 · 基础课第四课教学项目
> 公司、人物与事件均为虚构，对话内容由大模型实时生成，不代表任何真实主体。
