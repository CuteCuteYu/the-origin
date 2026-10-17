"""本地 JSON 文件存储：所有持久化都通过本模块，保证原子写入。"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
NPC_DIR = DATA_DIR / "npcs"
SAVE_DIR = DATA_DIR / "saves"
OA_DIR = DATA_DIR / "oa"
MOMENTS_DIR = DATA_DIR / "moments"


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
    """按 npc_id（如 npc_01）加载人设；路径做了白名单校验防目录穿越。"""
    path = NPC_DIR / f"{npc_id}.json"
    if not path.is_file():
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
    """清空全部对话存档与朋友圈缓存（AI 的全部记忆），返回删除的文件数。"""
    _ensure_dirs()
    count = 0
    for f in SAVE_DIR.glob("npc_*.json"):
        f.unlink()
        count += 1
    for f in MOMENTS_DIR.glob("npc_*.json"):
        f.unlink()
        count += 1
    return count


# ---------- 朋友圈缓存（AI 生成） ----------

def _moments_path(npc_id: str) -> Path:
    _ensure_dirs()
    return MOMENTS_DIR / f"{npc_id}.json"


def load_moments(npc_id: str) -> dict | None:
    data = load_json(_moments_path(npc_id))
    return data if isinstance(data, dict) else None


def save_moments(npc_id: str, payload: dict) -> None:
    save_json(_moments_path(npc_id), payload)
