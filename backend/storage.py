"""本地 JSON 文件存储：所有持久化都通过本模块，保证原子写入。

除人设 / 世界观 / OA 文档等静态数据外，运行时游戏状态全部落在
data/saves/ 目录下（对话存档、NPC 心理状态、记忆摘要、同事八卦、
访客口径、虚拟时钟、玩家笔记、OA 解锁记录），重置时整体清空。
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# 测试环境可通过环境变量把数据目录指到临时副本
DATA_DIR = Path(os.environ.get("THE_ORIGIN_DATA_DIR", Path(__file__).parent / "data"))
NPC_DIR = DATA_DIR / "npcs"
SAVE_DIR = DATA_DIR / "saves"
OA_DIR = DATA_DIR / "oa"
MOMENTS_DIR = DATA_DIR / "moments"

# saves/ 内的共享状态文件
GOSSIP_FILE = SAVE_DIR / "gossip.json"      # 同事间关于访客的议论（跨 NPC 传播）
CLAIMS_FILE = SAVE_DIR / "claims.json"      # 访客在各场合的「口径」清单
CLOCK_FILE = SAVE_DIR / "clock.json"        # 虚拟时钟（分钟数）
NOTES_FILE = SAVE_DIR / "notes.json"        # 玩家笔记（调查手记）
OA_STATE_FILE = SAVE_DIR / "oa_state.json"  # OA 文档解锁 / 已读（时间成本）记录


def _ensure_dirs() -> None:
    NPC_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    MOMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, payload: Any) -> None:
    """先写临时文件再替换，避免进程被杀时留下半截 JSON。"""
    _ensure_dirs()
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".tmp_", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, str(path))
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, payload: Any) -> None:
    _atomic_write(path, payload)


# ---------- 世界观与 NPC ----------

def load_world() -> dict:
    world = load_json(DATA_DIR / "world.json")
    if world is None:
        raise FileNotFoundError("缺少 data/world.json，请检查后端数据文件。")
    return world


def list_npc_files() -> list[Path]:
    _ensure_dirs()
    return sorted(NPC_DIR.glob("npc_*.json"))


def load_npc(npc_id: str) -> dict:
    """按 npc_id（如 npc_01）加载人设；校验路径确实落在 npcs/ 内防目录穿越。"""
    path = NPC_DIR / f"{npc_id}.json"
    if not path.is_file() or path.parent.resolve() != NPC_DIR.resolve():
        raise FileNotFoundError(f"NPC 不存在: {npc_id}")
    return load_json(path)


# ---------- OA 模拟系统文档 ----------

def load_oa_docs() -> list:
    """读取 data/oa/ 下全部文档文件（每个文件是一个文档数组），合并后按日期倒序返回。"""
    docs: list = []
    if OA_DIR.is_dir():
        for path in sorted(OA_DIR.glob("*.json")):
            data = load_json(path, default=[])
            if isinstance(data, list):
                docs.extend(data)
    docs.sort(key=lambda d: str(d.get("date", "")), reverse=True)
    return docs


# ---------- 对话存档 ----------

def _save_path(npc_id: str) -> Path:
    _ensure_dirs()
    return SAVE_DIR / f"{npc_id}.json"


def load_history(npc_id: str) -> list:
    data = load_json(_save_path(npc_id))
    return data if isinstance(data, list) else []


def save_history(npc_id: str, messages: list) -> None:
    save_json(_save_path(npc_id), messages)


def reset_all_saves() -> int:
    """清空全部运行时状态（saves/ 下的对话、心理状态、摘要、八卦、口径、
    时钟、笔记、OA 解锁），让一局游戏彻底回到初始状态。

    朋友圈缓存（moments/）不属于对局状态，保留复用：那是按 NPC 生成的
    AI 快照，重开一局直接复用即可，既省生成成本，也不会毁掉已有快照。
    返回删除的文件数。"""
    _ensure_dirs()
    count = 0
    for f in SAVE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


# ---------- NPC 心理状态与记忆摘要 ----------

def _npc_state_path(npc_id: str) -> Path:
    _ensure_dirs()
    return SAVE_DIR / f"{npc_id}_state.json"


def load_npc_state(npc_id: str) -> dict | None:
    data = load_json(_npc_state_path(npc_id))
    return data if isinstance(data, dict) else None


def save_npc_state(npc_id: str, state: dict) -> None:
    save_json(_npc_state_path(npc_id), state)


def _summary_path(npc_id: str) -> Path:
    _ensure_dirs()
    return SAVE_DIR / f"{npc_id}_summary.json"


def load_summary(npc_id: str) -> dict | None:
    data = load_json(_summary_path(npc_id))
    return data if isinstance(data, dict) else None


def save_summary(npc_id: str, data: dict) -> None:
    save_json(_summary_path(npc_id), data)


# ---------- 同事八卦 / 访客口径 ----------

def load_gossip() -> list:
    data = load_json(GOSSIP_FILE, default=[])
    return data if isinstance(data, list) else []


def save_gossip(items: list) -> None:
    save_json(GOSSIP_FILE, items)


def load_claims() -> list:
    data = load_json(CLAIMS_FILE, default=[])
    return data if isinstance(data, list) else []


def save_claims(items: list) -> None:
    save_json(CLAIMS_FILE, items)


# ---------- 虚拟时钟 ----------

def load_clock() -> dict | None:
    data = load_json(CLOCK_FILE)
    return data if isinstance(data, dict) else None


def save_clock(data: dict) -> None:
    save_json(CLOCK_FILE, data)


# ---------- 玩家笔记 ----------

def load_notes() -> dict:
    data = load_json(NOTES_FILE, default={})
    return data if isinstance(data, dict) else {}


def save_notes(notes: dict) -> None:
    save_json(NOTES_FILE, notes)


# ---------- OA 解锁 / 打开记录 ----------

def load_oa_state() -> dict:
    data = load_json(OA_STATE_FILE, default={})
    if not isinstance(data, dict):
        return {"unlocked": [], "opened": []}
    return {
        "unlocked": data.get("unlocked", []) or [],
        "opened": data.get("opened", []) or [],
    }


def save_oa_state(state: dict) -> None:
    save_json(OA_STATE_FILE, state)


# ---------- 朋友圈缓存（AI 生成） ----------

def _moments_path(npc_id: str) -> Path:
    _ensure_dirs()
    return MOMENTS_DIR / f"{npc_id}.json"


def load_moments(npc_id: str) -> dict | None:
    data = load_json(_moments_path(npc_id))
    return data if isinstance(data, dict) else None


def save_moments(npc_id: str, payload: dict) -> None:
    save_json(_moments_path(npc_id), payload)
