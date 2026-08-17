import re
from typing import Iterator

import httpx
from openai import OpenAI

from ..config import settings


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _openai_client(info: dict, injected=None) -> OpenAI:
    if injected is not None:
        return injected
    return OpenAI(api_key=info["api_key"] or "not-needed", base_url=info["base_url"])


def _anthropic_chat(
    info: dict, messages: list[dict], model: str, max_tokens: int
) -> str:
    system = "\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )
    rest = [
        {"role": message["role"], "content": message["content"]}
        for message in messages
        if message["role"] != "system"
    ]
    payload: dict = {"model": model, "max_tokens": max_tokens, "messages": rest}
    if system:
        payload["system"] = system
    response = httpx.post(
        info["base_url"].rstrip("/") + "/v1/messages",
        headers={"x-api-key": info["api_key"], "anthropic-version": "2023-06-01"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    text = "".join(
        block.get("text", "")
        for block in response.json().get("content", [])
        if block.get("type") == "text"
    )
    return strip_code_fences(text)


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int = 4000,
    json_mode: bool = True,
    stream: bool = False,
    provider: str | None = None,
    client=None,
) -> str | Iterator[str]:
    info = settings.provider_info(provider)
    model = model or settings.llm_model
    if info["provider"] == "anthropic":
        return _anthropic_chat(info, messages, model, max_tokens)

    llm = _openai_client(info, injected=client)
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if stream:
        kwargs["stream"] = True
        response = llm.chat.completions.create(**kwargs)

        def chunks() -> Iterator[str]:
            for chunk in response:
                content = chunk.choices[0].delta.content
                if isinstance(content, str) and content:
                    yield content

        return chunks()

    response = llm.chat.completions.create(**kwargs)
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("LLM 返回为空")
    return text
