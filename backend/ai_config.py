"""AI 玩家专用配置：只扫描系统中 ANTHROPIC* 前缀的环境变量。

与 config.py 完全隔离：
- 人类前端 / NPC 扮演（人类对局）继续使用 OPENAI* 配置；
- AI 前端（自主代理对局）只使用 ANTHROPIC* 配置，互不干扰。

支持的变量：
  ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN   密钥（任一即可）
  ANTHROPIC_BASE_URL                         端点，默认 https://api.anthropic.com
  ANTHROPIC_MODEL                            模型名，默认 glm-5.3
  ANTHROPIC_SMALL_FAST_MODEL                 情报鉴定用模型，默认同上
  ANTHROPIC_PROTOCOL                         anthropic / openai / auto（默认 auto）
"""

import os
import sys

# 默认模型（需求指定：模型默认使用 glm-5.3）
DEFAULT_MODEL = "glm-5.3"
DEFAULT_BASE_URL = "https://api.anthropic.com"


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def mask_secret(value: str) -> str:
    """对外展示用的密钥掩码（永远不要返回明文）。"""
    return _mask(str(value or ""))


def discover_anthropic_env() -> dict:
    """遍历进程环境变量，收集所有 ANTHROPIC 前缀的变量（大小写不敏感）。"""
    return {
        name: value
        for name, value in os.environ.items()
        if name.upper().startswith("ANTHROPIC")
    }


# 启动时立即执行发现
_ENV = discover_anthropic_env()

API_KEY = (
    _ENV.get("ANTHROPIC_API_KEY") or _ENV.get("ANTHROPIC_AUTH_TOKEN") or ""
).strip()
BASE_URL = (_ENV.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
MODEL = (_ENV.get("ANTHROPIC_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
JUDGE_MODEL = (
    _ENV.get("ANTHROPIC_SMALL_FAST_MODEL") or MODEL
).strip() or MODEL
PROTOCOL = (_ENV.get("ANTHROPIC_PROTOCOL") or "auto").strip().lower()

# 打印发现结果（值全部掩码，避免泄漏）
print("=" * 60)
print("[ai_config] 扫描系统环境变量中的 ANTHROPIC* 配置：")
if _ENV:
    for name, value in _ENV.items():
        print(f"  发现 {name} = {_mask(value)}")
else:
    print("  （未发现任何 ANTHROPIC* 环境变量）")
print(f"[ai_config] AI 玩家模型: {MODEL}（鉴定模型：{JUDGE_MODEL}）")
print(f"[ai_config] API 端点: {BASE_URL}")
print("=" * 60)

if not API_KEY:
    print(
        "[ai_config][警告] 未找到 ANTHROPIC_API_KEY。\n"
        "  AI 前端将无法启动自主对局（人类前端不受影响）。\n"
        "  请先在系统环境变量中设置，例如（PowerShell，永久生效）：\n"
        '  [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "你的key", "User")\n'
        "  如需自定义网关，再设置 ANTHROPIC_BASE_URL。",
        file=sys.stderr,
    )


def status() -> dict:
    """给前端的配置概览（不含明文密钥）。"""
    return {
        "ready": bool(API_KEY),
        "api_key_masked": _mask(API_KEY) if API_KEY else "",
        "base_url": BASE_URL,
        "model": MODEL,
        "judge_model": JUDGE_MODEL,
        "protocol": PROTOCOL,
        "env_names": sorted(_ENV.keys()),
    }


def assert_ready() -> None:
    """供 AI 路由 / LLM 层调用：缺少 key 时抛出可读异常。"""
    if not API_KEY:
        raise RuntimeError(
            "未配置 ANTHROPIC_API_KEY（或 ANTHROPIC_AUTH_TOKEN），无法启动 AI 自主对局。"
            "请设置系统环境变量后重启后端。"
        )
