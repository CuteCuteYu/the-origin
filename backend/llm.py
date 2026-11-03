"""LLM 调用封装：OpenAI 兼容接口，指向系统环境变量配置的端点。"""

from openai import OpenAI

import config

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        config.assert_ready()
        _client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.BASE_URL,
            timeout=60.0,
        )
    return _client


def chat(messages: list[dict], temperature: float = 0.85, max_tokens: int = 800) -> str:
    """发送对话请求，返回助手回复文本。

    温度稍高（0.85）是为了让角色扮演更自然有变化；max_tokens 限制回复长度，
    配合提示词里的'回复贴近真实聊天长度'约束，避免 NPC 写小作文。

    重要：glm-5.3 是推理模型，默认会先输出一大段思考（消耗 token 预算，
    极端情况下把预算耗尽导致正文为空）。角色扮演不需要长思考，
    因此显式关闭 thinking，回复更快、更省、也更贴近口语化人设。
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def chat_stream(messages: list[dict], temperature: float = 0.85, max_tokens: int = 800):
    """流式版本：逐段产出回复文本，用于前端打字机效果。

    部分网关会发送 choices 为空的保活事件，这里跳过它们。
    """
    client = _get_client()
    stream = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        extra_body={"thinking": {"type": "disabled"}},
    )
    for event in stream:
        choices = getattr(event, "choices", None)
        if not choices:
            continue
        delta = choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content
