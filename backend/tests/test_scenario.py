"""场景配置（scenario.json）测试：校验、编译、动态情报目标与重载接口。"""

import json
from pathlib import Path

import ai_intel
import scenario
import storage

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_example_scenario_is_valid():
    """随仓库提供的最小示例必须始终能通过校验。"""
    data = json.loads((DATA_DIR / "scenario.example.json").read_text(encoding="utf-8"))
    assert scenario.validate(data) == []


def _minimal_scenario(company_name="测试公司"):
    return {
        "meta": {
            "game_title": "测试游戏",
            "scene": "某写字楼 10 层",
            "game_clock": {"start": "16:00", "end": "19:00"},
        },
        "company": {"name": company_name, "industry": "测试行业"},
        "secret_project": {
            "name": "测试项目",
            "three_intel_targets": [
                {"target_id": "tech_stack", "name": "技术栈", "detail": "自研 + 国产芯片"},
                {"target_id": "launch_window", "name": "上线窗口", "detail": "三月试产"},
                {"target_id": "cost_floor", "name": "成本底线", "detail": "五折让价"},
            ],
        },
        "player": {"role": "测试调查员", "objective": "拿到测试情报"},
        "gm_rules": {"common_rules": ["测试规则"]},
        "ai_judge": {"acceptance_rules": ["测试规则"], "project_keywords": ["测试项目"]},
        "social_network": {
            "cast": {"npc_01": "测试员工", "publisher": "发行人"},
            "relations": [
                {
                    "from": "npc_01",
                    "to": "publisher",
                    "relation": "上下级 / 长期合作",
                    "from_view": "他只看数字。",
                    "to_view": "她能扛事，但太慢。",
                    "collaboration_history": ["一起做过一个项目"],
                    "social_events": [
                        {"date": "2026-01-01", "title": "复盘会", "summary": "测试事件"}
                    ],
                    "tension": "速度 vs 质量",
                    "trust": 60,
                    "visibility": "team",
                }
            ],
            "events": [
                {
                    "event_id": "evt_test",
                    "date": "2026-01-01",
                    "title": "复盘会",
                    "participants": ["npc_01", "publisher"],
                    "summary": "测试共同事件",
                    "impact": {"npc_01": "记得被追问进度"},
                    "visibility": "team",
                }
            ],
        },
        "npcs": [
            {
                "meta": {"id": "npc_01", "display_name": "测试员工", "title": "测试岗位"},
                "personality": {"core_traits": ["谨慎"]},
                "knowledge": {"public_facts": ["测试"]},
                "performance": {"meta_rules": ["测试"]},
            }
        ],
        "oa_documents": {
            "announcements": [
                {"id": "doc_test_1", "title": "测试公告", "blocks": []}
            ]
        },
    }


# ---------- 状态与校验 ----------


def test_social_network_validation_rejects_bad_shapes():
    data = _minimal_scenario()
    data["social_network"] = {
        "relations": [
            {
                "from": "npc_01",
                "to": "npc_01",
                "trust": 120,
                "visibility": "secret",
                "collaboration_history": "not-a-list",
            }
        ],
        "events": [
            {
                "title": "",
                "participants": [],
                "visibility": "secret",
                "impact": "not-a-dict",
            }
        ],
    }
    errors = scenario.validate(data)
    assert any("from 与 to" in error for error in errors)
    assert any("0-100" in error for error in errors)
    assert any("visibility" in error for error in errors)
    assert any("collaboration_history" in error for error in errors)
    assert any("participants" in error for error in errors)
    assert any("title" in error for error in errors)
    assert any("impact" in error for error in errors)


def test_npc_optional_sections_reject_bad_shapes():
    data = _minimal_scenario()
    data["npcs"][0]["relationships"] = ["not", "a", "dict"]
    data["npcs"][0]["records"] = {"entries": "not-a-list"}
    data["npcs"][0]["opinions_on_colleagues"] = [
        {"take": "缺少 about"},
        "not-a-dict",
    ]
    errors = scenario.validate(data)
    assert any("relationships" in error for error in errors)
    assert any("records.entries" in error for error in errors)
    assert any("opinions_on_colleagues[1]" in error for error in errors)
    assert any("opinions_on_colleagues[2]" in error for error in errors)


def test_shipped_scenario_is_valid_and_imported(client):
    info = scenario.status()
    assert info["exists"] is True
    assert info["errors"] == []
    assert info["up_to_date"] is True
    assert info["npc_count"] == 3
    assert info["doc_count"] == 18


def test_scenario_api_status_and_reload(client):
    status = client.get("/api/scenario/status")
    assert status.status_code == 200
    assert status.json()["exists"] is True

    res = client.post("/api/scenario/reload")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["applied"] is True
    assert body["npc_count"] == 3
    assert body["doc_count"] == 18


# ---------- 编译 ----------


def test_compile_custom_scenario_to_temp_dir(tmp_path):
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(
        json.dumps(_minimal_scenario(), ensure_ascii=False), encoding="utf-8"
    )

    result = scenario.compile_scenario(force=True, data_dir=tmp_path)
    assert result["ok"] is True and result["applied"] is True
    assert result["npc_count"] == 1
    assert result["doc_count"] == 1

    world = json.loads((tmp_path / "world.json").read_text(encoding="utf-8"))
    assert world["company"]["name"] == "测试公司"
    assert world["secret_project"]["three_intel_targets"][0]["target_id"] == "tech_stack"
    assert world["ai_judge"]["project_keywords"] == ["测试项目"]
    assert world["social_network"]["relations"][0]["from"] == "npc_01"
    assert world["social_network"]["cast"]["publisher"] == "发行人"

    npc = json.loads((tmp_path / "npcs" / "npc_01.json").read_text(encoding="utf-8"))
    assert npc["meta"]["display_name"] == "测试员工"

    docs = json.loads(
        (tmp_path / "oa" / "announcements.json").read_text(encoding="utf-8")
    )
    assert docs[0]["id"] == "doc_test_1"

    # 未修改配置时跳过
    again = scenario.compile_scenario(force=False, data_dir=tmp_path)
    assert again["applied"] is False
    assert again["reason"].startswith("场景配置未变化")

    # 生成文件被误删时，即使配置没变也应重新编译
    (tmp_path / "world.json").unlink()
    repaired = scenario.compile_scenario(force=False, data_dir=tmp_path)
    assert repaired["applied"] is True
    assert (tmp_path / "world.json").is_file()

    # 修改公司名后自动重新导入
    changed = _minimal_scenario(company_name="新公司")
    scenario_file.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    result = scenario.compile_scenario(force=False, data_dir=tmp_path)
    assert result["applied"] is True
    world = json.loads((tmp_path / "world.json").read_text(encoding="utf-8"))
    assert world["company"]["name"] == "新公司"


def test_invalid_scenario_is_rejected_without_writing(tmp_path):
    bad = _minimal_scenario()
    bad["secret_project"]["three_intel_targets"] = bad["secret_project"][
        "three_intel_targets"
    ][:2]
    (tmp_path / "scenario.json").write_text(
        json.dumps(bad, ensure_ascii=False), encoding="utf-8"
    )

    try:
        scenario.compile_scenario(force=True, data_dir=tmp_path)
    except scenario.ScenarioError as e:
        assert any("3 个情报目标" in err for err in e.errors)
    else:  # pragma: no cover
        raise AssertionError("应当抛出 ScenarioError")

    assert not (tmp_path / "world.json").exists()
    info = scenario.status(data_dir=tmp_path)
    assert info["errors"]


# ---------- AI 鉴定跟随配置 ----------


def test_ai_intel_uses_configured_targets(monkeypatch):
    world = _minimal_scenario()
    monkeypatch.setattr(storage, "load_world", lambda: world)

    progress = ai_intel.default_progress()
    assert set(progress["targets"]) == {"tech_stack", "launch_window", "cost_floor"}
    assert progress["total_count"] == 3

    names = [t["name"] for t in ai_intel.target_defs()]
    assert names == ["技术栈", "上线窗口", "成本底线"]

    brief = ai_intel.progress_brief(progress)
    assert "技术栈" in brief and "系统判定：未通关" in brief
