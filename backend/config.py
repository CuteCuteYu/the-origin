"""配置模块：启动时自动发现系统中的 OPENAI 前缀环境变量。"""

import os
import sys

# 固定使用的模型名
MODEL_NAME = "glm-5.3"

# 默认兜底端点（若系统未设置 OPENAI_BASE_URL 时使用）
_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def _mask(value: str) -> str:
    """对敏感值做掩码处理，仅用于日志打印。"""
    if len(value) <= 8:
        return "***"
    return value[:5] + "***" + value[-4:]


def discover_openai_env() -> dict:
    """遍历进程环境变量，收集所有 OPENAI 前缀的变量名与值。

    这样无论用户把 key 配在系统、用户还是会话级环境变量里，
    后端都能自动发现，无需修改代码。
    """
    found = {}
    for name, value in os.environ.items():
        if name.upper().startswith("OPENAI"):
            found[name] = value
    return found


# 启动时立即执行发现
_OPENAI_ENV = discover_openai_env()

API_KEY = _OPENAI_ENV.get("OPENAI_API_KEY", "")
BASE_URL = _OPENAI_ENV.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)

# 打印发现结果（值全部掩码，避免泄漏）
print("=" * 60)
print("[config] 扫描系统环境变量中的 OPENAI* 配置：")
if _OPENAI_ENV:
    for name, value in _OPENAI_ENV.items():
        print(f"  发现 {name} = {_mask(value)}")
else:
    print("  （未发现任何 OPENAI* 环境变量）")
print(f"[config] 使用模型: {MODEL_NAME}")
print(f"[config] API 端点: {BASE_URL}")
print("=" * 60)

if not API_KEY:
    print(
        "[config][错误] 未找到 OPENAI_API_KEY 环境变量。\n"
        "  请先在系统环境变量中设置它，例如（PowerShell，永久生效）：\n"
        '  [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "你的key", "User")\n'
        "  设置后重启终端 / VSCode 再启动本服务。",
        file=sys.stderr,
    )


def assert_ready() -> None:
    """供路由层调用：缺少 key 时抛出可读异常。"""
    if not API_KEY:
        raise RuntimeError(
            "未配置 OPENAI_API_KEY 环境变量，无法调用大模型。请设置后重启服务。"
        )
