"""Streaming adapter. Demo replies are templates, not model output."""

import os
from urllib.parse import urlparse

from companion.schema import system_prompt


def stream_reply(session, mode="demo"):
    if mode == "demo":
        for part in (f"你好，我是{session['nickname']}。", "这是离线演示回复，", "可以在侧栏切换到真实模型继续聊天。"):
            yield part
        return
    if mode != "live":
        raise ValueError("unsupported_mode")
    from openai import OpenAI

    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    key = os.environ.get("LLM_API_KEY", "")
    if not key:
        if urlparse(base_url).hostname in {"localhost", "127.0.0.1", "::1"}:
            key = "ollama"
        else:
            raise ValueError("missing_api_key")
    messages = [{"role": "system", "content": system_prompt(session)}, *session["messages"]]
    with OpenAI(base_url=base_url, api_key=key,
                timeout=float(os.environ.get("LLM_TIMEOUT_SECONDS", "60")), max_retries=0) as client:
        stream = client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "deepseek-r1:8b"), messages=messages, stream=True)
        try:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        finally:
            stream.close()
