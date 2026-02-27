"""Anthropic / Claude provider with message format conversion."""
from __future__ import annotations
import json
from anthropic import AsyncAnthropic
from .base import BaseLLMProvider, LLMResponse, ToolCall


def _to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split system prompt and convert OpenAI-format messages to Anthropic format."""
    system = ""
    out: list[dict] = []

    for msg in messages:
        role = msg["role"]

        if role == "system":
            system = msg["content"] or ""
            continue

        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
            continue

        if role == "assistant":
            if msg.get("tool_calls"):
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args)
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        }
                    )
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": "assistant", "content": msg.get("content", "")})
            continue

        if role == "tool":
            # Anthropic requires tool results inside a user message
            result_block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg["content"],
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(result_block)
            else:
                out.append({"role": "user", "content": [result_block]})

    return system, out


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"]["parameters"],
        }
        for t in tools
    ]


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key)

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        system, anthropic_messages = _to_anthropic_messages(messages)
        anthropic_tools = _to_anthropic_tools(tools) if tools else []

        kwargs: dict = dict(
            model=self.model,
            max_tokens=8096,
            system=system,
            messages=anthropic_messages,
        )
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, args=block.input or {})
                )

        content = "\n".join(text_parts) or None
        return LLMResponse(content=content, tool_calls=tool_calls)
