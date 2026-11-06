"""场景配置：用一份 `data/scenario.json` 定义「被测试的公司、环境与 NPC」。

这是场景的唯一事实来源。后端启动时（以及调用重载接口时）会把配置编译成
游戏运行所需的数据文件：

    data/world.json          ← meta / company / secret_project / player / gm_rules
                              + 可选的 ai_judge / social_network
    data/npcs/npc_XX.json    ← npcs[]
    data/oa/<category>.json  ← oa_documents{}

人类前端与 AI 前端都只读这些生成后的文件，因此换一家公司、换一批 NPC、
换一套 OA 文档，无需改任何代码。

设计要点：
- 配置未变化时跳过编译（哈希比对），不会反复覆盖手工修改；
- 编译只写入内容确实变化的文件；
- NPC 内容变化时清理该 NPC 的朋友圈缓存，避免旧快照串戏；
- 配置有误时抛出带明细的 ScenarioError，且不破坏现有数据。
"""

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import storage
import social

SCENARIO_FILENAME = "scenario.json"
STATE_FILENAME = ".scenario_state.json"

# 会写入 world.json 的世界观字段
WORLD_KEYS = ("meta", "company", "secret_project", "player", "gm_rules")

_NPC_ID_RE = re.compile(r"^npc_\d{2,3}$")
_TARGET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_CATEGORY_RE = re.compile(r"^[a-z0-9_\-]{1,40}$")


class ScenarioError(RuntimeError):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("场景配置有误：" + "；".join(self.errors))


# ---------- 路径与读取 ----------


def _base(data_dir=None) -> Path:
    return Path(data_dir) if data_dir else Path(storage.DATA_DIR)


def scenario_path(data_dir=None) -> Path:
    return _base(data_dir) / SCENARIO_FILENAME


def state_path(data_dir=None) -> Path:
    return _base(data_dir) / STATE_FILENAME


def load_scenario(data_dir=None) -> dict | None:
    path = scenario_path(data_dir)
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ScenarioError([f"无法读取 {path.name}：{e}"]) from e
    if not isinstance(data, dict):
        raise ScenarioError([f"{path.name} 顶层必须是一个 JSON 对象"])
    return data


def config_hash(data: dict) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------- 校验 ----------


def validate(data: dict) -> list[str]:
    errors: list[str] = []

    for key in WORLD_KEYS:
        if not isinstance(data.get(key), dict):
            errors.append(f"缺少对象字段 `{key}`")

    meta = data.get("meta") or {}
    if isinstance(meta, dict) and not str(meta.get("game_title") or "").strip():
        errors.append("`meta.game_title` 不能为空")

    company = data.get("company") or {}
    if isinstance(company, dict) and not str(company.get("name") or "").strip():
        errors.append("`company.name` 不能为空")

    targets = (data.get("secret_project") or {}).get("three_intel_targets")
    if not isinstance(targets, list) or len(targets) != 3:
        errors.append("`secret_project.three_intel_targets` 必须是恰好 3 个情报目标")
    else:
        seen_targets = set()
        for i, target in enumerate(targets, 1):
            if not isinstance(target, dict):
                errors.append(f"第 {i} 个情报目标必须是对象")
                continue
            tid = str(target.get("target_id") or "").strip()
            if not _TARGET_ID_RE.match(tid):
                errors.append(f"第 {i} 个情报目标的 target_id 非法：{tid!r}（小写字母/数字/下划线）")
            elif tid in seen_targets:
                errors.append(f"情报目标 target_id 重复：{tid}")
            seen_targets.add(tid)
            if not str(target.get("name") or "").strip():
                errors.append(f"情报目标 `{tid}` 缺少 name")

    npcs = data.get("npcs")
    if not isinstance(npcs, list) or not npcs:
        errors.append("`npcs` 必须是非空数组")
    else:
        seen_ids = set()
        for i, npc in enumerate(npcs, 1):
            if not isinstance(npc, dict):
                errors.append(f"第 {i} 个 NPC 必须是对象")
                continue
            npc_meta = npc.get("meta")
            if not isinstance(npc_meta, dict):
                errors.append(f"第 {i} 个 NPC 缺少 `meta` 对象")
                continue
            nid = str(npc_meta.get("id") or "").strip()
            if not _NPC_ID_RE.match(nid):
                errors.append(f"第 {i} 个 NPC 的 meta.id 非法：{nid!r}（应形如 npc_01）")
            elif nid in seen_ids:
                errors.append(f"NPC id 重复：{nid}")
            seen_ids.add(nid)
            if not str(npc_meta.get("display_name") or "").strip():
                errors.append(f"NPC `{nid}` 缺少 meta.display_name")
            for section in ("personality", "knowledge", "performance"):
                if not isinstance(npc.get(section), dict):
                    errors.append(f"NPC `{nid}` 缺少 `{section}` 对象")
            for section in ("basics", "duties", "background", "relationships", "side_details", "records"):
                if section in npc and not isinstance(npc.get(section), dict):
                    errors.append(f"NPC `{nid}` 的 `{section}` 必须是对象")
            records = npc.get("records")
            if isinstance(records, dict):
                entries = records.get("entries")
                if entries is not None and not isinstance(entries, list):
                    errors.append(f"NPC `{nid}` 的 `records.entries` 必须是数组")
            opinions = npc.get("opinions_on_colleagues")
            if opinions is not None:
                if not isinstance(opinions, list):
                    errors.append(f"NPC `{nid}` 的 `opinions_on_colleagues` 必须是数组")
                else:
                    for j, opinion in enumerate(opinions, 1):
                        if not isinstance(opinion, dict):
                            errors.append(
                                f"NPC `{nid}` 的 opinions_on_colleagues[{j}] 必须是对象"
                            )
                        elif not str(opinion.get("about") or "").strip():
                            errors.append(
                                f"NPC `{nid}` 的 opinions_on_colleagues[{j}] 缺少 about"
                            )

    network = data.get("social_network")
    if network is not None:
        if not isinstance(network, dict):
            errors.append("`social_network` 必须是对象")
        else:
            cast = network.get("cast")
            if cast is not None:
                if not isinstance(cast, dict):
                    errors.append("`social_network.cast` 必须是对象：{id: 显示名}")
                else:
                    for key, value in cast.items():
                        if not str(key or "").strip() or not str(value or "").strip():
                            errors.append("`social_network.cast` 的键与值都不能为空")

            relations = network.get("relations")
            if relations is not None:
                if not isinstance(relations, list):
                    errors.append("`social_network.relations` 必须是数组")
                else:
                    for i, rel in enumerate(relations, 1):
                        if not isinstance(rel, dict):
                            errors.append(f"`social_network.relations[{i}]` 必须是对象")
                            continue
                        a = str(rel.get("from") or "").strip()
                        b = str(rel.get("to") or "").strip()
                        if not a or not b:
                            errors.append(f"`social_network.relations[{i}]` 缺少 from/to")
                        elif a == b:
                            errors.append(f"`social_network.relations[{i}]` 的 from 与 to 不能相同")
                        for key in ("collaboration_history", "social_events"):
                            if key in rel and not isinstance(rel[key], list):
                                errors.append(
                                    f"`social_network.relations[{i}].{key}` 必须是数组"
                                )
                        trust = rel.get("trust")
                        if trust is not None and (
                            isinstance(trust, bool)
                            or not isinstance(trust, int)
                            or not 0 <= trust <= 100
                        ):
                            errors.append(
                                f"`social_network.relations[{i}].trust` 必须是 0-100 的整数"
                            )
                        visibility = str(rel.get("visibility") or "team").lower()
                        if visibility not in social.VISIBILITIES:
                            errors.append(
                                f"`social_network.relations[{i}].visibility` 只能是 public/team/private"
                            )

            events = network.get("events")
            if events is not None:
                if not isinstance(events, list):
                    errors.append("`social_network.events` 必须是数组")
                else:
                    seen_events: set[str] = set()
                    for i, event in enumerate(events, 1):
                        if not isinstance(event, dict):
                            errors.append(f"`social_network.events[{i}]` 必须是对象")
                            continue
                        eid = str(event.get("event_id") or "").strip()
                        if eid:
                            if eid in seen_events:
                                errors.append(
                                    f"`social_network.events` 的 event_id 重复：{eid}"
                                )
                            seen_events.add(eid)
                        participants = event.get("participants")
                        if not isinstance(participants, list) or not participants:
                            errors.append(
                                f"`social_network.events[{i}].participants` 必须是非空数组"
                            )
                        else:
                            for pid in participants:
                                if not str(pid or "").strip():
                                    errors.append(
                                        f"`social_network.events[{i}].participants` 不能包含空值"
                                    )
                        if not str(event.get("title") or "").strip():
                            errors.append(f"`social_network.events[{i}]` 缺少 title")
                        impact = event.get("impact")
                        if impact is not None and not isinstance(impact, dict):
                            errors.append(f"`social_network.events[{i}].impact` 必须是对象")
                        visibility = str(event.get("visibility") or "team").lower()
                        if visibility not in social.VISIBILITIES:
                            errors.append(
                                f"`social_network.events[{i}].visibility` 只能是 public/team/private"
                            )

    oa_docs = data.get("oa_documents")
    if oa_docs is not None:
        if not isinstance(oa_docs, dict):
            errors.append("`oa_documents` 必须是对象：{ 分类名: [文档, ...] }")
        else:
            seen_docs = set()
            for category, docs in oa_docs.items():
                if not _CATEGORY_RE.match(str(category)):
                    errors.append(f"OA 分类名非法：{category!r}")
                if not isinstance(docs, list):
                    errors.append(f"OA 分类 `{category}` 必须是数组")
                    continue
                for doc in docs:
                    if not isinstance(doc, dict):
                        errors.append(f"OA 分类 `{category}` 中存在非对象文档")
                        continue
                    did = str(doc.get("id") or "").strip()
                    if not did:
                        errors.append(f"OA 分类 `{category}` 中存在缺少 id 的文档")
                    elif did in seen_docs:
                        errors.append(f"OA 文档 id 重复：{did}")
                    seen_docs.add(did)
                    if not str(doc.get("title") or "").strip():
                        errors.append(f"OA 文档 `{did}` 缺少 title")

    ai_judge = data.get("ai_judge")
    if ai_judge is not None and not isinstance(ai_judge, dict):
        errors.append("`ai_judge` 必须是对象")

    return errors


# ---------- 编译 ----------


def _write_if_changed(path: Path, payload) -> bool:
    existing = storage.load_json(path, default=None)
    if existing == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    storage.save_json(path, payload)
    return True


def _remove_stale(folder: Path, keep: set[str], pattern: str) -> list[str]:
    removed = []
    if not folder.is_dir():
        return removed
    for path in folder.glob(pattern):
        if path.stem not in keep:
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed


def _count_docs(base: Path) -> int:
    count = 0
    oa_dir = base / "oa"
    if oa_dir.is_dir():
        for path in oa_dir.glob("*.json"):
            data = storage.load_json(path, default=[])
            if isinstance(data, list):
                count += len(data)
    return count


def _outputs_intact(base: Path, data: dict) -> bool:
    """配置没变但生成文件被删了时，仍应重新编译。"""
    if not (base / "world.json").is_file():
        return False
    for npc in data.get("npcs") or []:
        nid = str((npc.get("meta") or {}).get("id") or "").strip()
        if not nid or not (base / "npcs" / f"{nid}.json").is_file():
            return False
    oa_docs = data.get("oa_documents")
    if isinstance(oa_docs, dict):
        for category in oa_docs:
            if not (base / "oa" / f"{category}.json").is_file():
                return False
    return True


def compile_scenario(force: bool = False, data_dir=None) -> dict:
    """把 scenario.json 编译成游戏数据文件。

    force=False 时若配置哈希未变化则跳过（启动时使用）。
    配置有误时抛 ScenarioError，不写入任何文件。
    """
    base = _base(data_dir)
    path = scenario_path(base)
    result = {
        "ok": False,
        "applied": False,
        "path": str(path),
        "hash": "",
        "npc_count": 0,
        "doc_count": 0,
        "changed": [],
        "removed": [],
        "reason": "",
    }

    if not path.is_file():
        result["reason"] = f"未找到 {SCENARIO_FILENAME}，沿用现有数据文件。"
        return result

    data = load_scenario(base)
    errors = validate(data or {})
    if errors:
        raise ScenarioError(errors)

    digest = config_hash(data)
    result["hash"] = digest
    previous = storage.load_json(state_path(base), default={}) or {}
    if (
        not force
        and previous.get("hash") == digest
        and _outputs_intact(base, data)
    ):
        result.update(
            {
                "ok": True,
                "applied": False,
                "reason": "场景配置未变化，跳过导入。",
                "npc_count": len(data.get("npcs") or []),
                "doc_count": _count_docs(base),
                "last_import": previous.get("imported_at"),
            }
        )
        return result

    changed: list[str] = []
    removed: list[str] = []

    # 1) world.json
    world = {key: data[key] for key in WORLD_KEYS}
    if isinstance(data.get("ai_judge"), dict):
        world["ai_judge"] = data["ai_judge"]
    if isinstance(data.get("social_network"), dict):
        world["social_network"] = data["social_network"]
    if _write_if_changed(base / "world.json", world):
        changed.append("world.json")

    # 2) NPC 文件
    npc_dir = base / "npcs"
    npc_ids: list[str] = []
    changed_npcs: list[str] = []
    for npc in data["npcs"]:
        nid = str(npc["meta"]["id"]).strip()
        npc_ids.append(nid)
        # 写盘前去掉 id 中的空白，保证文件名与内容一致
        npc["meta"]["id"] = nid
        if _write_if_changed(npc_dir / f"{nid}.json", npc):
            changed.append(f"npcs/{nid}.json")
            changed_npcs.append(nid)

    stale_npcs = _remove_stale(npc_dir, set(npc_ids), "npc_*.json")
    removed.extend(f"npcs/{name}" for name in stale_npcs)
    changed_npcs.extend(Path(name).stem for name in stale_npcs)

    # 3) OA 文档（配置里给出 oa_documents 时才视为权威来源）
    oa_docs = data.get("oa_documents")
    doc_count = 0
    if isinstance(oa_docs, dict):
        oa_dir = base / "oa"
        for category, docs in oa_docs.items():
            doc_count += len(docs)
            # 文档列表所在的分类即权威分类，避免文件分组与字段不一致
            for doc in docs:
                if isinstance(doc, dict):
                    doc["category"] = category
            if _write_if_changed(oa_dir / f"{category}.json", docs):
                changed.append(f"oa/{category}.json")
        stale_oa = _remove_stale(oa_dir, set(oa_docs.keys()), "*.json")
        removed.extend(f"oa/{name}" for name in stale_oa)
    else:
        doc_count = _count_docs(base)

    # 4) NPC 变化后清理朋友圈缓存，避免旧快照与新 NPC 串戏
    for nid in sorted(set(changed_npcs)):
        moment = base / "moments" / f"{nid}.json"
        if moment.exists():
            try:
                moment.unlink()
            except OSError:
                pass

    imported_at = datetime.now().isoformat(timespec="seconds")
    state = {
        "hash": digest,
        "imported_at": imported_at,
        "npc_ids": npc_ids,
        "npc_count": len(npc_ids),
        "doc_count": doc_count,
    }
    storage.save_json(state_path(base), state)

    result.update(
        {
            "ok": True,
            "applied": True,
            "reason": "已从 scenario.json 导入场景。",
            "npc_count": len(npc_ids),
            "doc_count": doc_count,
            "changed": changed,
            "removed": removed,
            "last_import": imported_at,
        }
    )
    return result


# ---------- 状态与自动导入 ----------


def status(data_dir=None) -> dict:
    base = _base(data_dir)
    path = scenario_path(base)
    state = storage.load_json(state_path(base), default={}) or {}
    info = {
        "path": str(path),
        "filename": SCENARIO_FILENAME,
        "exists": path.is_file(),
        "hash": "",
        "imported_hash": state.get("hash", ""),
        "up_to_date": False,
        "last_import": state.get("imported_at"),
        "npc_count": state.get("npc_count", 0),
        "doc_count": state.get("doc_count", 0),
        "errors": [],
    }
    if not path.is_file():
        info["errors"].append(f"未找到 {SCENARIO_FILENAME}")
        return info
    try:
        data = load_scenario(base)
    except ScenarioError as e:
        info["errors"] = e.errors
        return info
    info["hash"] = config_hash(data or {})
    info["up_to_date"] = bool(info["hash"]) and info["hash"] == info["imported_hash"]
    if info["up_to_date"]:
        info["up_to_date"] = _outputs_intact(base, data or {})
    errors = validate(data or {})
    info["errors"] = errors
    return info


def auto_import() -> dict:
    """启动时调用：配置变了就自动导入；失败只记录，不阻止服务启动。"""
    try:
        result = compile_scenario(force=False)
    except ScenarioError as e:
        print("[scenario][错误] 场景配置未通过校验，沿用现有数据：", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return {"ok": False, "applied": False, "errors": e.errors}
    except Exception as e:  # 数据损坏 / 权限问题等
        print(f"[scenario][错误] 导入场景失败：{e}", file=sys.stderr)
        return {"ok": False, "applied": False, "errors": [str(e)]}

    if result.get("applied"):
        print(
            f"[scenario] 已导入场景：{result['npc_count']} 个 NPC，"
            f"{result['doc_count']} 份 OA 文档（共修改 {len(result.get('changed') or [])} 个文件）"
        )
    elif result.get("ok"):
        print("[scenario] 场景配置未变化，沿用已生成的游戏数据")
    else:
        print(f"[scenario] {result.get('reason', '未使用场景配置')}")
    return result
