"""场景配置接口：查看配置状态、手动重新导入。

配置文件：backend/data/scenario.json
- 后端启动时会自动检测配置是否变化并导入；
- 也可以调用 POST /api/scenario/reload 立即重载（例如运行中修改了配置）。
"""

from fastapi import APIRouter, HTTPException

import scenario

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.get("/status")
def scenario_status():
    """场景配置文件路径、哈希、最后导入时间与校验错误。"""
    return scenario.status()


@router.post("/reload")
def reload_scenario():
    """强制重新编译 scenario.json（导入失败时返回 400 与具体错误）。"""
    try:
        result = scenario.compile_scenario(force=True)
    except scenario.ScenarioError as e:
        raise HTTPException(status_code=400, detail="；".join(e.errors))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入场景失败：{e}")
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("reason") or "未找到 scenario.json，无法导入场景。",
        )
    return result
