"""AI 玩家的大模型客户端：只走 ANTHROPIC* 配置，零 SDK 依赖（标准库 urllib）。

为什么不用 openai SDK：AI 前端使用 ANTHROPIC 前缀配置，而这类网关既可能是
Anthropic Messages 协议，也可能是 OpenAI Chat Completions 协议。这里做了
双协议支持 + 自动探测：
  - anthropic: POST {base}/v1/messages（x-api-key + anthropic-version）
  - openai:    POST {base}/chat/completions（Authorization: Bearer）
auto 模式下先试 anthropic，遇到「路径 / 请求体不被识别」类错误时自动
回退到 openai，并在进程内记住可用协议。

人类前端的 llm.py 完全不受影响。
"""

import json
import time
import urllib.error
import urllib.request

from urllib.parse import urlsplit, urlunsplit

import ai_config

_ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT = 180
# 记住每个 base_url 探测成功的协议，后续请求直接复用
_PROTOCOL_CACHE: dict[str, str] = {}


class AILLMError(RuntimeError):
    """可直接展示给用户的模型调用错误。"""


class _HTTPFailure(Exception):
    def __init__(self, code: int, detail: str):
        super().__init__(f"HTTP {code}: {detail}")
        self.code = code
        self.detail = detail


class _TransportFailure(Exception):
    pass


# ---------- 模型档案 ----------


def _clean_base(base_url: str) -> str:
    return str(base_url or "").strip().rstrip("/")


def protocol_in_use(base_url: str, fallback: str = "auto") -> str:
    """返回某个 base_url 最近一次成功使用的协议，便于界面显示实际连通方式。"""
    return _PROTOCOL_CACHE.get(_clean_base(base_url), fallback)


def _safe_base(base_url: str) -> str:
    """去掉 URL 中的用户信息 / 查询串 / 片段，避免把密钥带进日志或事件。"""
    try:
        parts = urlsplit(str(base_url or "").strip())
    except ValueError:
        return ""
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def resolve_profile(kind: str = "agent", override: dict | None = None) -> dict:
    """解析一个模型档案（agent / game），支持界面传入的临时覆盖。

    override 既可以是 {"agent": {...}, "game": {...}}，也可以是扁平字段字典。
    空字符串字段自动回退到系统环境变量，保证「不填就用默认」。
    """
    kind = "game" if str(kind).lower() == "game" else "agent"
    profile = {
        "kind": kind,
        "api_key": ai_config.API_KEY,
        "base_url": _clean_base(ai_config.BASE_URL),
        "model": ai_config.MODEL,
        "judge_model": ai_config.JUDGE_MODEL if kind == "game" else ai_config.MODEL,
        "protocol": ai_config.PROTOCOL or "auto",
        "key_source": "env" if ai_config.API_KEY else "",
        "model_source": "env",
    }

    item: dict = {}
    if isinstance(override, dict):
        nested = override.get(kind)
        if isinstance(nested, dict):
            item = nested
        elif any(k in override for k in ("api_key", "base_url", "model", "protocol")):
            item = override

    for field in ("api_key", "base_url", "model", "protocol"):
        value = str(item.get(field) or "").strip()
        if not value:
            continue
        if field == "base_url":
            value = _clean_base(value)
        if field == "protocol":
            value = value.lower()
        profile[field] = value
        if field == "api_key":
            profile["key_source"] = "override"
        if field == "model":
            profile["model_source"] = "override"

    # 自定义了端点但没指定协议时，优先自动探测，避免被系统里的
    # ANTHROPIC_PROTOCOL 固定值锁死。
    if str(item.get("base_url") or "").strip() and not str(
        item.get("protocol") or ""
    ).strip():
        profile["protocol"] = "auto"

    if kind == "game":
        # 用户自定义游戏模型时，情报鉴定也使用同一个模型；
        # 未自定义时保留 ANTHROPIC_SMALL_FAST_MODEL 的默认行为。
        profile["judge_model"] = (
            profile["model"] if profile["model_source"] == "override"
            else ai_config.JUDGE_MODEL
        )
    else:
        profile["judge_model"] = profile["model"]

    return profile


def public_profile(profile: dict) -> dict:
    """可安全下发给前端 / 写入对局记录的档案摘要（不含密钥明文）。"""
    api_key = str(profile.get("api_key") or "")
    return {
        "kind": profile.get("kind", ""),
        "model": profile.get("model", ""),
        "judge_model": profile.get("judge_model", ""),
        "base_url": _safe_base(profile.get("base_url", "")),
        "protocol": profile.get("protocol", "auto"),
        "key_present": bool(api_key),
        "key_masked": ai_config.mask_secret(api_key) if api_key else "",
        "key_source": profile.get("key_source", ""),
        "model_source": profile.get("model_source", ""),
    }


# ---------- URL / 请求体组装 ----------


def _messages_url(base_url: str) -> str:
    base = _clean_base(base_url)
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return base + "/messages"
    return base + "/v1/messages"


def _chat_completions_url(base_url: str) -> str:
    base = _clean_base(base_url)
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _normalize(messages: list[dict]) -> tuple[str, list[dict]]:
    """把 OpenAI 风格的 messages 拆成 (system 文本, 严格 user/assistant 序列)。

    Anthropic 协议要求消息角色交替、以 user 开头，这里统一做合并与补齐，
    两种协议共用一份输入，避免调用方到处判断。
    """
    system_parts: list[str] = []
    convo: list[dict] = []
    for m in messages or []:
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
        if not content.strip():
            continue
        if role == "system":
            system_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            continue
        if convo and convo[-1]["role"] == role:
            convo[-1]["content"] += "\n\n" + content
        else:
            convo.append({"role": role, "content": content})

    if not convo:
        convo = [{"role": "user", "content": "继续。"}]
    if convo[0]["role"] != "user":
        convo.insert(0, {"role": "user", "content": "（开始）"})
    return "\n\n".join(system_parts), convo


def _payload(protocol: str, system: str, convo: list[dict], model: str,
             temperature: float, max_tokens: int, base_url: str) -> dict:
    # glm-5.3 是推理模型：不关 thinking 会先把 token 预算烧在思考上，
    # 极端情况下正文为空。角色扮演 / 情报鉴定都不需要长思考。
    no_thinking = {"thinking": {"type": "disabled"}}
    base = str(base_url or "").lower()
    zhipu_gateway = "bigmodel.cn" in base or "zhipu" in base

    if protocol == "anthropic":
        payload: dict = {
            "model": model,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "messages": convo,
        }
        if system:
            payload["system"] = system
        payload.update(no_thinking)
        return payload

    messages = ([{"role": "system", "content": system}] if system else []) + convo
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }
    # 智谱的 OpenAI 兼容端点支持该字段；其它 OpenAI 兼容网关不一定接受，故按域名限定
    if zhipu_gateway:
        payload.update(no_thinking)
    return payload


def _headers(protocol: str, api_key: str) -> dict:
    key = str(api_key or "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if protocol == "anthropic":
        headers["x-api-key"] = key
        headers["anthropic-version"] = _ANTHROPIC_VERSION
    # 部分网关只认 Bearer；官方 Anthropic 会忽略这个多余头部
    headers["Authorization"] = f"Bearer {key}"
    return headers


def _post(url: str, payload: dict, headers: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        raise _HTTPFailure(e.code, detail)
    except urllib.error.URLError as e:
        raise _TransportFailure(str(e.reason))
    except TimeoutError:
        raise _TransportFailure("请求超时")


def _extract_text(raw: str, protocol: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise AILLMError(f"模型返回的不是 JSON（前 200 字）：{raw[:200]}")

    if not isinstance(data, dict):
        raise AILLMError("模型返回格式异常（顶层不是对象）")

    # 网关有时在 200 里塞错误对象
    if data.get("error"):
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise AILLMError(f"模型服务返回错误：{msg}")

    # OpenAI 协议
    if isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0] or {}
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            return "".join(
                str(p.get("text", "")) for p in content if isinstance(p, dict)
            ).strip()
        return str(content or "").strip()

    # Anthropic 协议
    blocks = data.get("content")
    if isinstance(blocks, list):
        parts = []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") in ("text", "output_text"):
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()

    raise AILLMError(f"无法从模型响应中提取文本（协议={protocol}）")


# ---------- 对外接口 ----------


def chat_messages(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1200,
    profile: dict | None = None,
) -> str:
    """发送一次非流式对话，返回纯文本。

    profile 可以是 resolve_profile() 的结果；不传则使用系统环境变量中的
    agent 档案。messages 为 OpenAI 风格数组（可含 system）。
    """
    if not isinstance(profile, dict):
        profile = resolve_profile("agent")

    kind = profile.get("kind", "agent")
    api_key = str(profile.get("api_key") or "").strip()
    if not api_key:
        raise AILLMError(
            f"{kind} 模型未配置 API Key：请在 AI 前端「⚙ → 模型配置」中填写，"
            "或设置系统环境变量 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN。"
        )

    base_url = _clean_base(profile.get("base_url"))
    if not base_url.startswith(("http://", "https://")):
        raise AILLMError(f"{kind} 模型的 Base URL 无效：{base_url or '（空）'}")

    model = (model or profile.get("model") or ai_config.MODEL).strip() or ai_config.MODEL
    system, convo = _normalize(messages)

    profile_protocol = str(profile.get("protocol") or "auto").lower()
    explicit = profile_protocol in ("anthropic", "openai")
    if explicit:
        order = [profile_protocol]
    else:
        preferred = _PROTOCOL_CACHE.get(base_url) or "anthropic"
        order = [preferred, "openai" if preferred == "anthropic" else "anthropic"]

    errors: list[str] = []
    for protocol in order:
        url = (
            _messages_url(base_url)
            if protocol == "anthropic"
            else _chat_completions_url(base_url)
        )
        payload = _payload(
            protocol, system, convo, model, temperature, max_tokens, base_url
        )
        headers = _headers(protocol, api_key)
        try:
            try:
                raw = _post(url, payload, headers)
            except _TransportFailure:
                # 网络抖动重试一次，仍失败再换协议没有意义，直接抛
                time.sleep(1.0)
                raw = _post(url, payload, headers)
            try:
                text = _extract_text(raw, protocol)
            except AILLMError as e:
                # 网关可能在响应里回显密钥，错误信息统一脱敏
                raise AILLMError(str(e).replace(api_key, "***")) from None
            if not text:
                raise AILLMError(
                    "模型返回了空文本（可能触发了内容过滤或 token 预算耗尽）"
                )
            _PROTOCOL_CACHE[base_url] = protocol
            return text
        except _HTTPFailure as e:
            detail = e.detail.replace(api_key, "***") if api_key else e.detail
            errors.append(f"{protocol} @ {url} -> HTTP {e.code}：{detail[:300]}")
            # 鉴权类错误换协议也不会好，直接中断，避免重复失败
            if e.code in (401, 403):
                break
        except _TransportFailure as e:
            errors.append(f"{protocol} @ {url} -> 网络错误：{e}")

    raise AILLMError(
        f"{kind} 模型调用失败（model={model}，base_url={_safe_base(base_url)}）。\n"
        "请检查界面中的 API Key / Base URL / 模型名称，或系统环境变量。\n"
        + "\n".join(errors[-2:])
    )


def status() -> dict:
    """给前端的运行态信息：环境变量默认档案（不含密钥明文）。"""
    info = ai_config.status()
    agent = resolve_profile("agent")
    game = resolve_profile("game")
    info["profiles"] = {
        "agent": public_profile(agent),
        "game": public_profile(game),
    }
    info["protocol_in_use"] = (
        _PROTOCOL_CACHE.get(agent["base_url"]) or agent.get("protocol", "auto")
    )
    return info
