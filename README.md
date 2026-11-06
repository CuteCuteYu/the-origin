# 宇宙衍生本源 · the-origin

> **《宇宙衍生本源》（the-origin）· 商业调查档案** —— 一个「AI NPC 社交工程」对话游戏
>
> 你扮演一名商业调查员，用一场场对话，从一家公司员工的嘴里套出秘密项目的情报。

---

## 目录

- [游戏简介](#游戏简介)
- [界面预览](#界面预览)
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
  - [⑥ 游戏状态机](#6-游戏状态机gamestatepy)
- [API 参考](#api-参考)
- [数据文件格式](#数据文件格式)
- [自定义指南](#自定义指南)
- [更换 AI 对话模型](#更换-ai-对话模型)
- [开发笔记（踩坑记录）](#开发笔记踩坑记录)
- [常见问题](#常见问题)
- [扩展与二次开发](#扩展与二次开发)

---

## 游戏简介

《宇宙衍生本源》（the-origin）是一个由大语言模型实时驱动的文字对话游戏。

- **场景**：深圳市南山区智园大厦 14 楼，微芒科技（VigaNex）——一家 48 人的工业级边缘 AI 视觉模组公司；
- **你**：竞争对手派出的情报分析员，对外身份是「睿析咨询」的高级顾问，今天是你第三次到访公司；
- **NPC**：三名由 **glm-5.3** 实时扮演的公司员工，拥有完整人设档案、长期记忆与警觉机制；
- **目标**：套出秘密项目「启明计划」的三块情报拼图（技术路线 / 量产时间表 / 报价底线）；
- **特色**：公司还挂着一套模拟 OA 系统，里面藏着 18 份从人设推导出的内部文档——公告、会议纪要、周报、群聊归档、项目复盘。**先侦查，再开口。**

> 系统不会判定胜负。什么时候算「拿到手」，由你自己判断。

---

## 界面预览

> 以下截图均为 1920×1080 的实际运行界面，完整文件位于 [`screenshots/`](screenshots/)。

### 人类前端（玩家调查沙盘）

#### 1. 访谈室主界面

![人类前端主界面](screenshots/human-01-main.png)

左侧是任务简报、情报拼图自评与访谈名单；中间是访谈室，按 NPC 的可用时段约人；顶栏显示虚拟时钟、档案编号与重置入口。

#### 2. 真实 NPC 对话

![人类前端 NPC 对话](screenshots/human-02-chat.png)

输入开场白后，NPC 依据人设、关系网、知识边界与当前信任 / 警觉实时回复；每轮推进 5 分钟，名单上的「已记录 N 问」与数值同步更新。

#### 3. OA 系统：文档列表

![人类前端 OA 文档列表](screenshots/human-03-oa.png)

18 份文档按公告通知、会议纪要、日志周报、通讯记录、项目档案分类；带 🔒 的文档需要口令，未读数与阅读状态会保留。

#### 4. OA 文档阅读器

![人类前端 OA 文档阅读](screenshots/human-04-oa-doc.png)

公告、周报、群聊、复盘统一由 8 种内容块渲染；首次打开文档消耗 2 分钟，正文与作者、日期、标签都来自场景配置。

#### 5. 调查笔记本

![人类前端调查笔记本](screenshots/human-05-notebook.png)

口径档案自动记录你对不同 NPC 说过的自我陈述；通用备忘与按人物分栏的观察记录保存在后端存档，重启不丢。

#### 6. NPC 朋友圈

![人类前端 NPC 朋友圈](screenshots/human-06-moments.png)

朋友圈由 AI 依据人设、关系网与合作经历生成，包含动态、点赞与同事评论；首次生成后缓存，可手动刷新覆盖。

### AI 前端（自主操作员终端）

> AI 对局截图使用固定决策演示，便于稳定展示界面；实际游玩仍由大模型实时决策。

#### 1. 待命主界面

![AI 前端待命界面](screenshots/ai-01-dashboard.png)

左侧是任务指令、目标名册与历史对局；中间是行动链；右侧是情报板与代理记忆。顶栏显示 AGENT / GAME 两套模型与实际协议。

#### 2. 一次完整自主对局

![AI 前端行动链与最终报告](screenshots/ai-02-action-chain.png)

代理自动完成「思考 → 读文档 → 情报鉴定 → 阶段推进 → 收束」，行动链保留每一步的理由、动作与反馈；右侧生成最终情报报告。

#### 3. 控制台设置：事件与阅读偏好

![AI 前端设置：事件类型](screenshots/ai-04-settings-events.png)

可按事件类型显隐行动链、切换舒适 / 紧凑密度、新事件置顶、自动滚动、思考 / 文档默认折叠。

#### 4. 控制台设置：双模型配置

![AI 前端设置：双模型](screenshots/ai-05-settings-models.png)

AGENT 负责进攻决策与最终报告，GAME 负责 NPC 扮演与情报鉴定；两套模型可分别覆盖 API Key、Base URL 与模型名，留空回退 `ANTHROPIC*` 环境变量，并可单独测试连接。

#### 5. 控制台设置：过滤预设与场景

![AI 前端设置：过滤与场景](screenshots/ai-06-settings-filters.png)

过滤预设可自定义行动链的可见事件组合；场景配置区显示 `scenario.json` 的导入状态、NPC / 文档规模与校验错误，可立即重新导入。

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
- **信任 / 警觉双数值**：每轮对话后 NPC 会更新对你的信任度与警觉度（聊天窗顶部实时可见）。信任 <50 不释放深层信息；≥60 且警觉 ≤40 才可能吐露 layer2；layer3 需要信任 ≥75 且警觉 ≤25；警觉拉满后只剩官话。**同一话术反复使用会逐渐失效**（NPC 会记住你用过几遍）；
- **办公室传话**：NPC 之间会互相议论你。陈静中午听到的八卦，下午周明远就会知道——在一个人面前说错话，代价是全局的；
- **口径追踪**：你自报的身份、雇主、来意都会被记录进「口径档案」（笔记本里可查），并注入后续所有 NPC 的提示词做交叉比对。**对两个人说不同的谎是最快的翻车方式**；
- **时间经济**：一天只有 16:00–19:00。每轮对话花 5 分钟，首次打开一份 OA 文档（或口令解锁一份加密文档）花 2 分钟；陈静 17:30 下班、周明远 18:30、方雨桐 19:00 闭园才走。问什么、先问谁，都是取舍；
- **受限文档**：18 份 OA 文档中有 3 份带 🔒（涉密私聊归档、算法组纪要、联席会纪要），需要口令解锁——线索藏在对话与白板角落里，乱试会被系统记录；
- **来源警觉**：如果外部顾问说出只有内部才有的细节，NPC 会立刻追问「你从哪知道的」——引用 OA 材料是双刃剑，方式得当是敲门砖，方式鲁莽是催命符；
- **长期记忆**：NPC 记得你之前说过的每一句话（包括你随口报的名字），只有「销毁记录」才会失忆。超长对话会自动压缩成前情摘要，NPC「记大意」但不忘关键口径。

### 推荐游玩路线

> 注意时间：一轮对话 5 分钟，全时长只够约 36 句话（还要扣掉翻文档的时间）。别浪费在寒暄上。

1. **先逛 OA 系统**：读周报、纪要、群聊，记下每个人在乎什么、介意什么；顺手找找受限文档的口令线索（解锁一份计 2 分钟，与普通文档首开同价）；
2. **与陈静（16:00 · 前台，17:30 下班）聊**：她是八卦枢纽，初始信任最高，能拿到「启明」代号、剧本杀事件、「那个数字」等钩子，并告诉你该去找谁；
3. **攻周明远（17:00 · 会议室 B，18:30 下班）**：用技术共鸣（产线、散热、标定）打开他的话匣子，深挖「历史原因」；
4. **最后见方雨桐（18:00 · 会议室 A，19:00 闭园）**：她是守关 BOSS（初始信任仅 25 / 警觉 30），需要你带着从其他两人处获得的真实碎片，通过她的「诚实度测试」与「你要拿它做什么」的评估；
5. **随时翻笔记本**：口径档案会列出你说过的每一句自我介绍——换人之前先核对，别让两个人听到两个版本的「你」。

---

## 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | React 18 + Vite 5 | 三视图：访谈室（SSE 流式聊天）+ OA 模拟系统 + 笔记本 |
| 后端 | Python 3.10+ / FastAPI + uvicorn | 12 个人类接口 + 6 个 AI 接口 + 2 个场景接口；人类逻辑集中在 6 个 Python 文件，AI / 场景为独立模块 |
| 环境管理 | uv | `uv sync` / `uv run` |
| 存储 | 本地 JSON 文件 | 无数据库；人设、世界观、OA 文档、全部运行时状态都是 JSON |
| 模型 | glm-5.3 | 人类前端自动扫描 `OPENAI*`；AI 前端自动扫描 `ANTHROPIC*`（默认模型同为 glm-5.3） |
| 测试 | pytest + httpx（TestClient） | 53 个用例：状态机 / 提示词遮蔽 / API 全链路（假模型注入，不需要 API Key） |

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
  发现 OPENAI_API_KEY = abcd***wxyz
  发现 OPENAI_BASE_URL = https***/v4
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

### 5. 运行测试（可选）

```powershell
cd backend
uv run pytest
```

53 个用例覆盖：存储层读写与重置、`<state>` 解析与心理状态合并、八卦 / 口径沉淀与跨 NPC 注入、虚拟时钟与下班边界、口令归一化、提示词的世界真相遮蔽（`499` 绝不出现）、API 全链路（SSE 流 / 409 / 解锁计时 / 加密文档 open 拒绝 / 笔记 / 重置）。测试通过 `THE_ORIGIN_DATA_DIR` 把数据目录指向临时副本并注入假模型，**不需要 API Key，也不会碰真实存档**。

---

## 界面与功能

> 整体视觉采用**微信配色**：深色灰阶基底（#111111 / #191919 / #2C2C2C）、微信绿主色（#07C160）、微信风格绿色聊天气泡（#3EB575）、微信红（#FA5151）用于「机密」与警示；三名 NPC 分别使用微信橙 / 蓝 / 黄作为识别色。

### 访谈室（默认视图）

- 与 NPC 的实时对话（**SSE 流式输出**，回复逐字浮现）；`Enter` 发送，`Shift + Enter` 换行；
- 聊天窗顶部有**信任 / 警觉双量表**，每轮对话后实时变化；
- NPC 回复中的（动作/神态描写）以斜体渲染，表演感更强；
- 等待回复时有打字指示器（每个 NPC 有专属文案，如「方雨桐正在评估你的问题……」）；
- 对方下班或 19:00 闭园后，输入区禁用并出现横幅提示；
- 首条对话前提供三句通用开场白，也可直接输入。

### OA 模拟系统（VigaOA）

- 顶部标签切换进入；窗口栏、保密标签、「内部资料」水印齐备；
- **5 大分类、18 份文档**：公告通知 ×3、会议纪要 ×3、日志与周报 ×4、通讯记录 ×5、项目档案 ×3；
- **受限文档**：3 份涉密文档带 🔒 标记，点开后是口令解锁面板（附线索提示）；口令可从访谈、群聊归档、白板涂鸦里挖出来；
- **未读红点计数**（localStorage 持久化）、**搜索**（标题/作者/标签）、面包屑导航；
- 首次打开一份文档（含口令解锁）会让游戏时钟走 2 分钟（时间就是情报成本）；聊天气泡的时间显示的是游戏内虚拟时钟，不是你的真实时间。

### 笔记本（第三视图）

- **口径档案**：自动记录你在各人面前说过的、被对方记下的自我陈述——这些话会被注入其他 NPC 的提示词交叉比对，说谎前先看一眼；
- **我的手记**：按人物分栏的 textarea + 通用备忘，保存在后端存档（重启不丢），用来记时间线、口令线索和待验证的疑点。

### NPC 朋友圈（AI 生成）

- 左侧「访谈名单」卡片右上角点击「朋友圈」进入（微信朋友圈风格界面：封面、头像、动态流）；
- 动态由 AI 依据人设**现场生成**：吐槽加班、美食奶茶、家人与周末、小感慨，以及同事们的点赞与评论（评论者与语气严格符合人物关系）；
- 首次打开需 10~30 秒生成，之后缓存到 `backend/data/moments/`，再次进入秒开；「刷新动态」会先二次确认再覆盖缓存（旧快照不可恢复）；
- 「销毁记录 · 重新开始」只清空对局状态，**朋友圈缓存保留复用**——重开一局不会毁掉已生成的快照，也省一次生成成本。

### 左侧任务简报（常驻）

- 背景掩护与行动目标；「随身资源」可折叠；
- **情报拼图自评勾选框**（localStorage 持久化，勾满三块会出现「该收网了」提示）；
- **访谈名单**：显示每位 NPC 的**可用性徽章**（🟢 可聊到几点 / 🔴 已下班）、信任 / 警觉数值与「已记录 N 问」，点击任意人物自动切回访谈室。

### 顶部操作

- **虚拟时钟**：`⏱ 16:35 / 19:00`——一眼看清今天还剩多少时间；
- 「销毁记录 · 重新开始」：二次确认后清空**全部运行时状态**（对话存档、心理数值、八卦与口径、时钟、笔记、OA 解锁记录、已读状态、拼图勾选；朋友圈缓存保留），游戏回到 16:00 的初始状态。

---

## 项目架构

### 目录结构

```
code/
├── README.md                      # 本文档
├── start.ps1                      # 一键启动脚本（纯 ASCII 英文，避免乱码）
├── backend/
│   ├── pyproject.toml             # uv 项目配置（fastapi / uvicorn / openai + dev: pytest/httpx）
│   ├── main.py                    # FastAPI 入口：人类路由 + AI/场景路由挂载 + 静态托管
│   ├── config.py                  # 启动时扫描 OPENAI* 环境变量（掩码打印）
│   ├── llm.py                     # OpenAI 兼容客户端封装（glm-5.3，流式 + 关闭 thinking）
│   ├── prompt_builder.py          # ★ 提示词组装器：人设 JSON → 15 层 system prompt
│   ├── gamestate.py               # ★ 游戏状态机：信任/警觉、八卦、口径、时钟、OA 解锁
│   ├── storage.py                 # JSON 原子读写（world / npcs / oa / saves / moments / AI 对局）
│   ├── scenario.py                # ★ 场景配置编译：scenario.json → world / npcs / oa
│   ├── scenario_api.py            # /api/scenario/*（状态 / 重新导入）
│   ├── ai_config.py               # AI 前端专用 ANTHROPIC* 环境变量发现
│   ├── ai_llm.py                  # Anthropic / OpenAI 双协议客户端
│   ├── ai_intel.py                # 情报鉴定、阶段反馈、最终报告
│   ├── ai_game.py                 # AI 可调用的游戏动作层
│   ├── ai_agent.py                # 自主代理循环
│   ├── ai_api.py                  # /api/ai/*（SSE 对局、中止、历史）
│   ├── tests/                     # pytest 套件（假模型注入，无需 API Key）
│   │   ├── conftest.py            # 数据目录指向临时副本 + 存档自动清理 + TestClient
│   │   ├── test_storage.py
│   │   ├── test_gamestate.py
│   │   ├── test_prompt_builder.py
│   │   ├── test_api.py
│   │   ├── test_ai.py
│   │   └── test_scenario.py
│   └── data/
│       ├── scenario.json          # ★ 场景唯一事实来源：公司 / 环境 / NPC / OA / 鉴定规则
│       ├── scenario.example.json  # 最小示例模板（复制为 scenario.json 即可开新局）
│       ├── world.json             # 生成产物：世界观 / 秘密项目 / GM 规则 / 游戏时钟
│       ├── npcs/                  # 生成产物：npc_01 陈静 / npc_02 周明远 / npc_03 方雨桐
│       ├── oa/                    # 生成产物：OA 模拟系统文档（3 份受限）
│       ├── saves/                 # 运行时生成：对话存档、心理状态、摘要、八卦、口径、时钟、笔记、OA 状态
│       └── moments/               # 运行时生成：朋友圈动态缓存（AI 生成）
└── frontend/
    ├── package.json / vite.config.js / index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                # 状态与数据流（三视图切换、SSE 流式、游戏状态聚合、重置）
        ├── api.js                 # 后端接口封装（含 SSE 流解析）
        ├── styles.css             # 微信配色主题（深色）+ OA + 朋友圈 + 量表/锁/笔记本样式
        └── components/
            ├── BriefingPanel.jsx  # 任务简报 + 情报拼图
            ├── NPCList.jsx        # 访谈名单（可用性徽章 + 心理数值 + 朋友圈入口）
            ├── ChatWindow.jsx     # 聊天窗口（流式渲染 / 双量表 / 下班横幅 / 打字指示）
            ├── OAWindow.jsx       # OA 系统（分类 / 搜索 / 已读 / 🔒 解锁面板）
            ├── OABlocks.jsx       # OA 文档内容块渲染器（8 种 block 类型）
            ├── NotebookPanel.jsx  # 笔记本（口径档案 + 玩家手记）
            └── MomentsModal.jsx   # 朋友圈弹窗（AI 生成动态 / 点赞 / 评论）

AI_frontend/                         # 面向 AI 的自主操作员终端（零构建，后端托管在 /ai）
    ├── index.html                   # 控制台骨架 + 视图设置面板
    ├── styles.css                   # 仪表盘 / 情报板 / 行动链 / 设置面板样式
    ├── app.js                       # SSE 消费、事件渲染、自定义过滤、历史回放
    └── README.md                    # 使用说明
```

### 一次对话的完整数据流

```
玩家输入
  → POST /api/npcs/{id}/chat（SSE）
  → 校验可用性（下班/闭园 → 409）→ 时钟 +5 分钟 → 用户消息立即落盘
  → 读取 world.json + npc_XX.json + 历史存档 + 心理状态 + 同事八卦 + 访客口径 + 前情摘要
  → prompt_builder 组装 15 层 system prompt
  → 流式调用 glm-5.3，逐段回传 data:{"type":"delta"} 事件
  → 解析末尾 <state>{信任/警觉/话术/八卦/口径}</state> 并剥离正文
  → 状态合并落盘；八卦/口径汇入共享池（下次其他 NPC 的提示词可见）
  → 历史超 40 条时把旧消息压缩进前情摘要（只携带近 20 条原文）
  → data:{"type":"done"} 收尾（附最新时钟与心理状态）→ 前端刷新聚合视图
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

> 顶层可选字段 `social_network` 用结构化数据描述 NPC 之间的合作经历、共同事件与双方视角；
> 它会进入 NPC 提示词、朋友圈生成，以及 AI 玩家的公开关系简报。字段说明见 [`SCENARIO.md`](SCENARIO.md)。

### 2. 信息三层分级机制

`knowledge.secrets_by_layer` 把机密分成三层，每层条目都带「出现的时机」与「表达参考」：

- **layer1**：初次见面就能自然聊到的氛围信息（如陈静抱怨「研发区装了门禁，我送快递都要登记」）；
- **layer2**：聊熟了、问对方向、或对方显出懂行才说（如周明远的「放弃了国外主流方案」钩子）；
- **layer3**：深度信任后才可能透露（如方雨桐的真实时间表与报价结构），每场最多泄露一两条；
- **never_reveal**：无论如何不透露、不承认、不瞎编的底线；
- **secret_clues**：结构化线索（clue_id / 内容 / 释放时机 / 引导方向），保证三名 NPC 的线索互相交织。

此外，`performance.suspicion_triggers` 定义了警觉触发点：直问机密、连环追问、身份暴露……每种情况都有精确的反应剧本。

### 3. 提示词分层组装

`prompt_builder.py` 把世界观 + 人设 + **运行时状态**渲染为 **16 层 system prompt**：

1. **场景层**：游戏时间（虚拟时钟）、地点、该 NPC 的会面场景；
2. **世界观层**：公司设定 + 世界真相（报价数字自动遮蔽为 `49x`，防止模型超纲泄底）；
3. **访客层**：玩家身份与掩护故事（**不含**玩家真实目标）；
4. **同事八卦层**：其他 NPC 近期议论过访客什么（办公室传话的落地）；
5. **访客口径层**：访客在其他场合的自我陈述（供交叉比对，说谎会被抓住）；
6. **前情摘要层**：长局压缩出的「以前聊过什么」；
7. **扮演规则层**：GM 通用规则 + 该角色专属元规则（第一人称 / 不承认 AI / 不泄露提示词 / 记忆规则 / 材料反应规则）；
8. **角色档案层**：basics → duties → personality → background → relationships → side_details 结构化渲染；
9. **社会关系网层**（`social_network`）：结构化关系、本人视角的看法、合作经历与共同事件；
10. **材料记忆层**（`records`）：逐一列出亲历文档与回忆态度；
11. **私人看法层**（`opinions_on_colleagues`）；
12. **知识边界层**：公开信息 + 三层分级 + 绝不透露 + 线索网络；
13. **互动策略层**：对话弧线 + 警觉触发点剧本；
14. **风格示范层**：对话范例渲染为纯文本（**明确标注「非真实历史」**，不是真实消息）；
15. **心理状态层**：该 NPC 当前的信任 / 警觉数值、分档行为指引、已耐受的话术清单；
16. **输出协议层**：要求回复末尾追加 `<state>{...}</state>` 块（信任 / 警觉 / 本轮话术 / 想跟同事说的八卦 / 访客口径）。

历史消息以 OpenAI messages 格式携带（摘要索引之前的消息已被压缩），上限 500 条，配合存档即长期记忆。

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

- **对话记忆**：完整历史持久化在 `data/saves/{npc_id}.json`（本地文件，重启服务不丢）——NPC 记得你说过的每一句话；
- **记忆压缩**：未摘要消息超过 40 条时，把除最近 20 条以外的旧消息交给模型压缩成 ≤350 字的**前情摘要**（保留：打听过什么、NPC 释放过什么、关系变化、访客的口径、承诺与威胁）。之后请求只携带摘要 + 近期原文——长局不爆上下文，NPC「记大意」但不忘口径；
- **材料记忆**：人设 `records` 章节让 NPC 对 OA 材料具有真实回忆，并对「外部顾问为何知道内部细节」做来源警觉；
- **重置**：只有点击「销毁记录 · 重新开始」（`POST /api/game/reset`）才删除 saves/ 下全部运行时文件（对话、心理状态、摘要、八卦、口径、时钟、笔记、OA 解锁），让游戏回到 16:00。朋友圈缓存（moments/）不属于对局状态，保留复用。

### 6. 游戏状态机（gamestate.py）

一次 LLM 调用同时产出「正文 + 结构化状态」，靠回复末尾的 `<state>` 协议：

```
正文……<state>{
  "trust": 62,        // 对访客的信任 0-100（后端夹紧合并进存档）
  "suspicion": 8,     // 警觉 0-100
  "tactic": "礼貌寒暄", // 本轮对方使用的话术（重复使用会累积耐受）
  "gossip": "前台来了个自称咨询顾问的人",  // 想跟同事说的（进共享八卦池）
  "claims": ["访客自称来自睿析咨询"]        // 访客的自我陈述（进口径档案）
}</state>
```

后端解析后：剥离正文落盘（玩家永远看不到协议块）、合并心理状态、把八卦与口径汇入共享池（**只注入其他 NPC 的提示词**——自己说过的已在对话历史里）。分档规则随状态层写进提示词：信任 <50 不放 layer2，≥60 且警觉 ≤40 可放，layer3 要 ≥75/≤25，警觉 ≥85 只剩官话。

**虚拟时钟**：`world.json` 的 `meta.game_clock` 配置起止与每轮耗时；`saves/clock.json` 存当前分钟数。NPC 的 `meta.available_until` 决定各自下班时间，不可用时对话接口返回 409。

**OA 解锁**：受限文档声明 `access.passphrase`（校验忽略大小写与空白）；解锁前接口不返回 `blocks`/`preview`，口令永不外泄；解锁即首次阅读，推进时钟 2 分钟（未解锁直接 `open` 返回 403，不计时）。

---

## API 参考

| 方法 | 路径 | 说明 | 返回示例 |
| --- | --- | --- | --- |
| GET | `/api/game/briefing` | 任务简报（公开信息 + 情报拼图名称） | `{ meta, company, player, intel_targets }` |
| GET | `/api/game/state` | 聚合运行时状态：时钟、各 NPC 可用性与心理数值、口径档案、笔记、OA 解锁 | `{ clock, day_over, npcs, claims, notes, unlocked_docs, ... }` |
| POST | `/api/game/reset` | 清空全部运行时状态（saves/；朋友圈缓存保留），回到 16:00 | `{ ok: true, removed_files: 5 }` |
| PUT | `/api/game/notes` | 保存玩家调查笔记 | `{ ok: true, notes: {...} }` |
| GET | `/api/npcs` | NPC 名单（仅展示层信息，绝不泄露人设） | `{ npcs: [{ id, display_name, available_until, ... }] }` |
| GET | `/api/npcs/{id}/history` | 某 NPC 的完整对话历史（已剥离 `<state>` 块） | `{ npc_id, messages: [{ role, content, ts }] }` |
| POST | `/api/npcs/{id}/chat` | 发一句话，**SSE 流式**返回（下班/闭园时 409） | 见下方事件说明 |
| GET | `/api/oa/documents` | OA 全部文档（受限文档解锁前不含 blocks/preview，永不返回口令） | `{ documents: [ ... ] }` |
| POST | `/api/oa/open` | 记录打开文档；首次打开推进时钟 2 分钟（加密文档未解锁时 403） | `{ ok, first_time, clock, day_over }` |
| POST | `/api/oa/unlock` | 口令解锁受限文档；解锁即首次阅读，推进时钟 2 分钟（口令错误 403） | `{ ok, doc: {...}, clock, day_over }` |
| GET | `/api/npcs/{id}/moments` | 朋友圈动态（无缓存时现场 AI 生成并缓存） | `{ npc_id, generated_at, posts: [...] }` |
| POST | `/api/npcs/{id}/moments/refresh` | 重新生成朋友圈动态（覆盖缓存） | 同上 |

`/chat` 的 SSE 事件流：

```
data: {"type": "delta", "text": "（她抬起头"}     ← 增量正文，逐段推送
data: {"type": "delta", "text": "……）你好"}        ← ……
data: {"type": "done", "reply": "…",              ← 完整干净正文（无 state 块）
       "clock": "16:05", "day_over": false,
       "npc_info": {"trust": 62, "suspicion": 8, "available": true, ...}}
data: {"type": "error", "message": "模型调用失败：…"} ← 仅失败时
```

调试示例（PowerShell）：

```powershell
# 聚合状态（时钟 / 心理数值 / 口径）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/game/state" | ConvertTo-Json -Depth 5

# 与陈静对话（SSE，PowerShell 下直接拿到整段事件流文本）
$body = @{ message = "陈静你好，今天想聊几句。" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/npcs/npc_01/chat" -Method Post -Body $body -ContentType "application/json"
```

---

## 数据文件格式

> 从 1.3 起，`world.json` / `npcs/npc_XX.json` / `oa/*.json` 都是 `scenario.json` 的**生成产物**。
> 自定义场景请改 [`backend/data/scenario.json`](SCENARIO.md)，保存后重启后端会自动导入。

### world.json（世界观）

```jsonc
{
  "meta": {
    "game_title": "宇宙衍生本源", "current_date": "2026-10-16", "scene": "...",
    "game_clock": { "start": "16:00", "end": "19:00", "minutes_per_chat": 5, "minutes_per_doc": 2 }
  },
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
  "meta": {
    "id": "npc_01", "display_name": "陈静", "title": "行政前台", "emoji": "🌸",
    "available_until": "17:30"          // 下班时间；到点后该 NPC 不可再聊（409）
  },
  "performance": {
    "initial_state": { "trust": 55, "suspicion": 5 }   // 初始心理值（守关 BOSS 可设得更警觉）
  },
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
  "access": {                            // 可选：受限文档（前端显示 🔒，接口隐藏正文直到解锁）
    "restricted": true,
    "passphrase": "QM",                  // 校验忽略大小写与首尾空白
    "lock_hint": "口令是项目组的内部代号，两个字母，就写在会议室 B 白板的角落里。",
    "reason": "含未公开项目信息的联席会纪要"
  },
  "blocks": [
    { "type": "meta", "items": [["时间", "2026-10-13（周二）10:00 - 11:35"], ["地点", "会议室 B"]] },
    { "type": "quote", "text": "我不管工程复杂度，我只要节点。", "source": "——方雨桐" },
    { "type": "callout", "tone": "warn", "text": "本纪要含未公开项目信息，严禁转发。" }
  ]
}
```

---

## 自定义指南

> 场景的唯一事实来源是 `backend/data/scenario.json`。修改 `world.json` /
> `npcs/npc_XX.json` / `oa/*.json` 只会在下一次导入时被覆盖。
> 完整字段说明与最小示例见 [`SCENARIO.md`](SCENARIO.md)。

### 修改人设（最常用）

编辑 `scenario.json` → `npcs[]` 中对应的 NPC：

- 改性格 → `personality.speech_style` / `catchphrases`；
- 改说话风格 → `performance.few_shot_examples`（风格示范，注意它们**不是**真实对话）；
- 调信息释放时机 → `knowledge.secrets_by_layer` 各条目的 `when` / `how_to_say`；
- 新增材料记忆 → `records.entries`。

保存后重启后端，或调用 `POST /api/scenario/reload`；校验失败会在响应与
`GET /api/scenario/status` 中给出具体字段。

### 新增 OA 文档

1. 编辑 `scenario.json` → `oa_documents.<分类>` 追加一个文档对象；若要做成**受限文档**，加上 `access` 节（`restricted` / `passphrase` / `lock_hint` / `reason`），并在某个 NPC 的 layer 信息或群聊归档里埋下口令线索；
2. 如果希望 NPC「记得」它，把条目写进相关 NPC 的 `records.entries`；
3. 重新导入后刷新页面即可看到。已读状态按文档 `id` 记录，切勿重复。

### 调整难度与节奏

- **时间压力**：改 `scenario.json -> meta.game_clock`（缩短整天、或把每轮对话调成 10 分钟）；
- **NPC 上下班**：改 `npcs[].meta.available_until`；
- **初始好感**：改 `npcs[].performance.initial_state`（例如让守关角色初始警觉 50，难度立刻上升）；
- **数值分档**：分档规则在 `gamestate.py` 的 `state_summary_for_prompt`（写进提示词的文案）。

### 新增第四名 NPC

1. 复制 `scenario.json` 里现有的一个 `npcs[]` 元素，改 `meta.id` 为 `npc_04`，重写全部内容（记得 `meta.available_until` 与 `performance.initial_state`）；
2. 在 `company.org_structure` 中补充该人物在公司结构里的位置；
3. 若涉及新线索，在其余 NPC 的 `relationships` / `records` 中同步提及（保持一致性）；
4. 无需改任何代码——导入后前端自动出现新名单。

## 更换 AI 对话模型

> 本项目通过 **OpenAI 兼容接口**调用大模型，任何提供 OpenAI 风格 Chat Completions 接口的服务都可以接入——各大云厂商、聚合平台、甚至本地模型（Ollama / vLLM 等）。更换模型**只需改环境变量与一个常量**，无需改动任何业务代码，前端也不受影响。

### 模型配置的三个要素

| 要素 | 配置位置 | 说明 |
| --- | --- | --- |
| 模型名 | `backend/config.py` 的 `MODEL_NAME` | 发给接口的 `model` 参数，如 `glm-5.3` |
| API 端点 | 环境变量 `OPENAI_BASE_URL` | 不设置时默认智谱 BigModel 端点 |
| API 密钥 | 环境变量 `OPENAI_API_KEY` | 启动时自动扫描，日志中只显示掩码 |

### 第一步：设置环境变量（PowerShell，永久生效）

以 DeepSeek 为例：

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "你的key", "User")
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", "https://api.deepseek.com/v1", "User")
# 设置后必须重启终端 / VSCode 才会生效
```

### 第二步：修改模型名

编辑 `backend/config.py`：

```python
MODEL_NAME = "deepseek-chat"
```

**可选进阶**：把模型名也改为环境变量驱动，之后换模型完全不用碰代码：

```python
MODEL_NAME = os.environ.get("OPENAI_MODEL", "glm-5.3")
```

### 第三步：重启后端并验证

`Ctrl + C` 停掉后端后重新启动，观察启动日志：

```
[config] 使用模型: deepseek-chat
[config] API 端点: https://api.deepseek.com/v1
```

然后与任意 NPC 说一句话，或直接调接口验证：

```powershell
$body = @{ message = "你好" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/npcs/npc_01/chat" -Method Post -Body $body -ContentType "application/json"
```

### 常见平台速查表

| 平台 | OPENAI_BASE_URL | MODEL_NAME 示例 | 备注 |
| --- | --- | --- | --- |
| 智谱 BigModel | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.3`、`glm-4.7` | 项目默认；glm-5.3 是推理模型（见下方注意事项） |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | 性价比高，中文对话自然 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`、`gpt-4o-mini` | 需海外网络与付费账号 |
| 月之暗面 Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k`、`kimi-k2` | 长上下文友好 |
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`、`qwen-max` | 需开通百炼服务 |
| 硅基流动等聚合平台 | 见平台文档 | 平台支持的各模型名 | 一个 key 使用多家模型 |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` 等本地模型名 | 完全离线可玩；`OPENAI_API_KEY` 设为任意非空字符串即可 |

### 推理模型注意事项（重要）

部分模型（如智谱 glm-5.3、DeepSeek-R1 类推理模型）默认先输出一大段“思考”再给正文，思考会消耗 `max_tokens` 预算，极端情况下正文为空。本项目在 `backend/llm.py` 中显式关闭了思考：

```python
extra_body={"thinking": {"type": "disabled"}}
```

换模型时：

- 新模型**是**推理模型 → 保留该参数；
- 新模型**不是**推理模型 → 一般可保留（多数网关会忽略未知字段）；但个别平台（如 OpenAI 官方）对未知字段会报错 `Unrecognized request argument`，此时改为按端点条件启用：

```python
extra = {"thinking": {"type": "disabled"}} if "bigmodel" in config.BASE_URL else {}
response = client.chat.completions.create(
    model=config.MODEL_NAME,
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens,
    extra_body=extra,
)
```

- 换模型后若出现**空回复** → 先调大 `max_tokens` 再排查。

### 调整回复风格（backend/llm.py）

| 参数 | 默认值 | 作用 | 调整建议 |
| --- | --- | --- | --- |
| `temperature` | `0.85` | 随机性 | 调低（0.5~0.7）人设更稳定；调高更活泼但易跑偏 |
| `max_tokens` | `800` | 单条回复长度上限 | 回复被截断或为空时调大；嫌 NPC 话多可调小 |

朋友圈动态生成固定使用 `temperature=0.95`、`max_tokens=1600`（见 `main.py` 的 `_generate_moments`），追求内容多样性。

### 故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 启动报「未找到 OPENAI_API_KEY」 | 环境变量未设置或未生效 | 按「快速开始」设置后重启终端 |
| 401 Unauthorized | key 错误/过期，或与端点不匹配 | 核对 key 与 `OPENAI_BASE_URL` 是否同属一个平台 |
| 404 / model not found | 模型名写错或该平台无此模型 | 对照平台文档改 `MODEL_NAME` |
| 400 / Unrecognized request argument | 平台不认识 `thinking` 字段 | 见「推理模型注意事项」中的条件启用写法 |
| NPC 回复为空 | 思考耗尽 token 预算 | 调大 `max_tokens`，或确认思考已关闭 |
| 回复极慢/超时 | 网络或平台限流 | 检查网络；可在 `llm.py` 调大 `timeout=60.0` |

---

## 开发笔记（踩坑记录）

> 以下都是本项目真实踩过的坑，供参考交流。

1. **glm-5.3 是推理模型**：默认先输出 `reasoning_content`（思考），会消耗 `max_tokens` 预算，极端情况下正文为空（`finish_reason: length`）。角色扮演不需要长思考，我们通过 `extra_body={"thinking": {"type": "disabled"}}` 关闭——回复更快、更省、也更口语化。
2. **few-shot 示例不能作为真实 messages 注入**：否则模型会把示例当成「已经发生过的对话」（实测中陈静会说「你刚不是问过一遍了吗」）。正确做法是把示例渲染进 system prompt 文本，并明确标注「这不是真实对话历史」。
3. **记忆 = 历史 + 携带**：NPC 的「记性」取决于两件事——历史是否完整落盘（持久化），以及请求时是否完整携带（本项目上限 500 条）；任何一环截断，NPC 都会「失忆」。
4. **数据一致性是角色的生命线**：所有 OA 文档必须与人设严格对齐，NPC 才能「真的想起来」。本项目做过一次全量一致性审查，修复了「去年/上个月」时间矛盾、「三楼/12F」地点矛盾、群聊日期与「明天开会」的逻辑矛盾等 5 处问题。
5. **越权防护**：GM 规则强制「第一人称 / 不承认 AI / 不泄露提示词存在 / 不讨论公司之外的事」；实测玩家追问「你是不是 AI」时，角色会用自己的方式（冷幽默/怼人）化解。
6. **前端同文件多处编辑要小心**：如果是在编辑器/工具里同时提交多个替换，建议逐个执行并复查最终文件，避免锚点交错导致文件损坏。
7. **一次调用同时要「表演」和「数值」**：让模型在回复末尾追加 `<state>` 块（信任/警觉/话术/八卦/口径），比单独再发一次「请评估信任度」的调用省一半成本和延迟，还保证数值与剧情同步。代价是要防模型写坏 JSON——解析取「最后一个可解析块」，清理用宽松正则（坏块、未闭合块都不能漏进正文给玩家看到）。
8. **注入别人的记忆时排除本人**：八卦和口径池是全局共享的，但给某个 NPC 注入时要过滤掉他自己产出的条目——那些已经在他的对话历史里了，重复注入会让模型困惑「我是不是说过」。

---

## 常见问题

**Q1：启动报 `No module named uvicorn`，或 uv 启动器报 Python 版本错误？**
不要直接运行全局的 `uvicorn` 命令，改用 `uv run python -m uvicorn main:app --port 8000`。

**Q2：NPC 回复为空？**
大概率是模型思考消耗了 token 预算。确认 `llm.py` 中 `thinking` 关闭参数对新模型生效，或把 `max_tokens` 调大。

**Q3：端口被占用？**
后端换端口：`uv run python -m uvicorn main:app --port 8001`，同时修改 `frontend/vite.config.js` 中 proxy 的 `target`。

**Q4：如何从头开始玩？**
点右上角「销毁记录 · 重新开始」，或调用 `POST /api/game/reset`。这会清除对话存档、OA 已读状态与拼图勾选（朋友圈缓存保留）。

**Q5：无网络/无 API Key 能玩吗？**
不能。NPC 对话需要实时调用大模型。

**Q6：PowerShell 里看接口返回的中文是乱码？**
那是控制台编码问题，数据本身是 UTF-8。让脚本把结果写入文件后用编辑器查看，或先执行 `chcp 65001`。

**Q7：改了人设为什么不生效？**
后端需要以 `--reload` 启动才能自动重载；手动重启后端亦可。如果对话中途修改，已建立的历史消息仍保留。

**Q8：运行 `start.ps1` 提示「无法加载文件……在此系统上禁止运行脚本」？**
这是 Windows 脚本执行策略的限制。请使用 `powershell -ExecutionPolicy Bypass -File .\start.ps1` 运行（见「快速开始 · 一键启动」），或先执行一次 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

---

## AI 自动游玩前端（AI_frontend）

> 给 AI 玩的版本：用户只提一次要求，代理自己读文档、找人套话、判断情报价值，直到全部情报目标都 confirmed。

- **入口**：启动后端后访问 <http://127.0.0.1:8000/ai/>（静态页面由 FastAPI 直接托管，无需 npm 安装 / 构建）；
- **模型配置（双模型）**：默认读取系统环境变量里的 `ANTHROPIC*`；也可在 AI 前端 `⚙ → 模型配置` 中分别填写「AI 玩家（进攻/报告）」与「游戏环境（NPC/鉴定）」的 API Key、Base URL、模型名。留空字段自动回退环境变量；两套模型可以指向不同网关。密钥只保存在当前标签页 `sessionStorage`，不写入对局记录；每套模型都有「测试连接」按钮，可先验证再开跑；
- **人类前端不受影响**：`/api/*` 的对局逻辑未改动，AI 侧全部走新增的 `/api/ai/*`；
- **明确胜负**：新增情报鉴定器，每次对话 / 读文档后返回 `valid_info`、命中目标、`partial / confirmed`、缺口与阶段；配置中的全部情报目标都 confirmed 即判定通关并生成报告；
- **行动链自定义**：右上角 `⚙` 可按事件类型显隐、创建过滤预设、切换舒适/紧凑密度、新事件置顶、自动滚动、思考/文档默认折叠；偏好保存在浏览器 `localStorage`；
- **共享存档**：AI 与人类共用同一份 `data/saves/`，重开一局前记得勾选「重置存档（清空进度）」；
- **公开关系图**：AI 玩家只拿到 `visibility=public` 的 NPC 关系与共同事件（例如公开冲突），用来决定先找谁、向谁打听谁；`team` / `private` 的私下关系不会进入 AI 简报；
- **接口**：`GET /api/ai/briefing`、`GET /api/ai/status`、`POST /api/ai/play`（SSE）、`POST /api/ai/test-llm`、`POST /api/ai/stop`、`GET /api/ai/runs`；
- **详细说明**：见 [`AI_frontend/README.md`](AI_frontend/README.md)。

---

## 场景配置（公司 / 环境 / NPC）

被测试的公司、环境、NPC、OA 文档与 AI 鉴定规则统一收敛在：

```
backend/data/scenario.json
```

- 修改保存后，**重启后端会自动导入**（按配置哈希判断是否需要重新编译）；
- 也可以调用 `POST /api/scenario/reload`，或在 AI 前端 `⚙ → 场景配置` 里立即重新导入；
- 导入会生成 `world.json`、`npcs/npc_XX.json`、`oa/<category>.json` —— 这些是生成产物，不要直接编辑；
- 配置校验失败时不会覆盖现有数据，错误会打印在控制台并可通过 `GET /api/scenario/status` 查看；
- 最少需要提供 `meta`、`company`、`secret_project`（恰好 3 个情报目标）、`player`、`gm_rules`、`npcs`；
- 字段说明、最小示例、NPC 模板与排查清单见 [`SCENARIO.md`](SCENARIO.md)。

### 用 AI 生成 `scenario.json`（提示词教程）

`scenario.json` 通常是十几万字符量级的 JSON，手写容易漏字段。推荐让 AI 分两步生成：**先定大纲，再出 JSON，最后按校验错误迭代**。

#### 第 1 步：让 AI 出设定大纲（不写 JSON）

```text
你是《宇宙衍生本源》（the-origin）的场景设计师。请先不要输出 JSON，用表格给出一个商业调查游戏的设定大纲：
- 被调查公司：行业、规模、地点、近期公开事件、内部紧张点
- 玩家身份与掩护故事
- 恰好 3 个机密情报目标（名称 + 一句话真相 + 获取路线）
- 3 个 NPC（姓名/职位/性格/下班时间/各自掌握哪一层信息/相互矛盾或传话的点）
- NPC 之间的关系网：至少 3 组关系（亲近 / 冲突 / 合作各一组），每组写双方视角、合作经历、共同事件与张力
- 至少 8 份 OA 文档的清单（标题/类型/日期/是否受限/口令线索藏在谁的对话里）
- 难度设定：初始信任/警觉、每轮对话耗时、闭园时间
要求：虚构，不要使用真实公司或真人；信息之间要能互相印证，不能自相矛盾。
```

#### 第 2 步：让 AI 输出完整 JSON

确认大纲后，用下面的模板（尖括号内容替换成你的设定）：

```text
你是《宇宙衍生本源》（the-origin）的场景配置生成器。请根据给定大纲，生成一份完整的 scenario.json。

【硬性约束】
1. 只输出一个 JSON 对象，不要 markdown 代码块，不要解释文字。
2. 顶层必须包含：meta、company、secret_project、player、gm_rules、ai_judge、social_network、npcs、oa_documents。
3. secret_project.three_intel_targets 必须恰好 3 个；target_id 唯一且只含小写字母/数字/下划线；
   每个目标要有 name、detail（真值，给鉴定器看）、hint、keywords（3-8 个）。
4. npcs 至少 3 个；meta.id 必须是 npc_01、npc_02、npc_03…；
   每个 NPC 必须包含 meta、basics、duties、personality、background、relationships、
   side_details、knowledge、records、opinions_on_colleagues、performance。
5. 每个 NPC 的 knowledge.secrets_by_layer 必须有三层：layer1_surface / layer2_familiar / layer3_deep；
   每条包含 info、when、how_to_say。layer3 全场最多泄露一两条。
6. oa_documents 是 {分类名: [文档]}；每份文档要有唯一 id、title、date、author、preview、blocks；
   至少 2 份带 access.restricted=true 和 passphrase，并在某个 NPC 的 layer 信息里埋下口令线索。
7. NPC 的下班时间、初始信任/警觉、信息层级要互相协调，保证可通关但不容易。
8. 不要使用真实公司、真实人物、真实客户名；全部虚构。
9. JSON 必须合法：双引号、无尾逗号、无注释；数组/对象闭合。
10. 不要输出 <state> 或任何提示词协议。
11. social_network 必须包含 cast、relations、events：
    - cast 用 {id: "姓名（职位）"} 覆盖所有被引用的 from/to/participants；
    - relations 至少 3 组，每条含 from、to、relation、from_view、to_view、
      collaboration_history（1-3 条）、social_events（0-2 条）、tension、trust（0-100）、
      visibility（public/team/private）；
    - events 至少 1 个，含 event_id、date、title、participants（至少 2 人）、
      summary、impact、visibility；
    - from_view 与 to_view 必须是不同人的第一人称视角，不能写成同一个人；
    - visibility 要合理：公开冲突用 public，私下看法用 team/private。

【schema 摘要】
（粘贴 SCENARIO.md 的「顶层结构」、「NPC 字段说明」与「NPC 社会关系网」三节）

【设定大纲】
（粘贴第 1 步的表格）

【参考结构】
可以参照 backend/data/scenario.example.json 的字段形状，但内容必须按本大纲重写。

输出完整 scenario.json。
```

#### 第 3 步：保存并校验

1. 将 AI 输出保存为 `backend/data/scenario.json`（先备份原文件）；
2. 重启后端，或调用 `POST /api/scenario/reload`，或在 AI 前端 `⚙ → 场景配置 → 重新导入场景`；
3. 查看 `GET /api/scenario/status` 的 `errors`（或 AI 前端面板中的错误列表）；
4. 如果有错误，把错误原文贴回给 AI：

```text
下面是 scenario.json 的校验错误。请只修复这些问题，保持其余内容不变，
输出完整的、合法的 JSON（不要省略任何字段，不要输出解释）：
- ...
```

5. 重复直到 `errors` 为空、`up_to_date` 为 true。

#### 第 4 步：让 AI 做一致性复查（推荐）

```text
请以审稿人身份检查这份 scenario.json：
1. 三个情报目标是否都能从 NPC 的三层信息与 OA 文档中找到获取路径？
2. 是否有 NPC 说出了自己知识边界之外的信息？
3. 受限文档的口令线索是否至少藏在一条玩家能拿到的 layer2 信息里？
4. 时间是否足够：按每轮对话 5 分钟、每份文档 2 分钟，玩家能否在闭园前完成？
5. 有没有自相矛盾的人名、日期、部门、金额？
6. social_network 里的 from_view / to_view 是否分别符合两个当事人的性格，且没有把同一句话复制给双方？
7. public / team / private 的可见性是否合理（公开冲突 public，私下看法 team/private）？
只列出问题与修改建议，不要重写全文。
```

#### 生成时的实用技巧

- **分块生成**：如果模型输出被截断，先让它单独生成 `npcs` 数组，再单独生成 `oa_documents`，最后用脚本合并；比一次输出十几万字符更稳。
- **先小后大**：先用 `scenario.example.json`（1 个 NPC、1 份文档）跑通，再让 AI 扩写到 3 个 NPC、8+ 份文档。
- **让它自查 JSON**：要求「输出前检查括号、逗号与引号」；内容太长时宁可减少一份文档，也要保证 JSON 合法。
- **只让它改配置**：配置生成只输出 `scenario.json`，不要让 AI 修改 `backend/*.py`。
- **关系网单独生成**：先让 AI 用表格列出「谁—谁—关系—合作过什么—共同事件—公开/私下」，再转成 `social_network.relations` / `events`，能显著减少关系自相矛盾。
- **不要写密钥**：`scenario.json` 只放世界设定；模型密钥在 AI 前端的「模型配置」中填写。

#### 验收清单

- [ ] 恰好 3 个 `three_intel_targets`，`target_id` 唯一
- [ ] `npcs[].meta.id` 唯一且形如 `npc_01`
- [ ] 每个 NPC 有 `personality` / `knowledge` / `performance`
- [ ] `social_network.cast` 覆盖所有 `from` / `to` / `participants`
- [ ] 至少 3 组 `relations`，包含合作经历 / 共同事件 / 双方视角
- [ ] `from_view` 与 `to_view` 是不同人的视角，且没有把私下看法写成公开信息
- [ ] `visibility` 使用合理：公开冲突 `public`，私下关系 `team` / `private`
- [ ] 每个 `layer1/2/3` 都有 `info` / `when` / `how_to_say`
- [ ] 受限文档有 `access.passphrase`，且口令线索可获取
- [ ] 情报目标的 `detail` 与 NPC 台词能对应上
- [ ] 时间为 16:00–19:00，NPC 下班时间与剧情一致
- [ ] 没有真实公司 / 真人 / 真实客户
- [ ] JSON 合法，`/api/scenario/status` 无错误

---

## 扩展与二次开发

本项目涉及的技术点：

- **前端**：React 组件拆分、状态提升、双视图路由、localStorage 持久化、CSS 设计系统；
- **后端**：FastAPI 路由设计、Pydantic 校验、CORS、分层模块（config / storage / llm / prompt_builder）；
- **工程化**：uv 环境管理、前后端代理联调、JSON 数据驱动、原子写文件；
- **提示词工程**：角色扮演的人设结构、信息分层控制、防越权规则、few-shot 的正确注入位置、长期记忆设计。

**欢迎尝试的改造方向**：

1. 设计第 4 名 NPC（部门自选），并让他的线索与现有三人交织；
2. 为 OA 系统增加「一键引用到对话」按钮（把文档摘要贴进聊天输入框）；
3. 把 JSON 存储替换为 SQLite，并保持接口签名不变；
4. **多结局收网**：19:00 闭园后让玩家提交情报结论，按口径一致性 / 解锁文档数 / 各 NPC 信任度生成「情报复盘报告」（数据已全部就绪，只差结算接口与报告页）；
5. 增加一个「来电」事件：对话中途 NPC 接电话，短暂离线后带回新信息；
6. 话术耐受的可视化：`tactics_used` 已在后端计数，可画成热力图提示玩家「这招快用老了」。

---

> 宇宙衍生本源 · the-origin
> 公司、人物与事件均为虚构，对话内容由大模型实时生成，不代表任何真实主体。
