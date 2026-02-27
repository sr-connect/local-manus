"""
OpenAI-compatible provider — covers both OpenAI and Ollama.

Ollama exposes the OpenAI Chat Completions API at /v1, so the same
client code works for both; only the base_url and api_key differ.

Includes a text-fallback parser: some smaller models output tool calls
as JSON text ("finish_reason: stop") instead of using the native
function-calling mechanism. We detect and handle this gracefully.
"""
from __future__ import annotations
import json
import re
import uuid
from openai import AsyncOpenAI
from .base import BaseLLMProvider, LLMResponse, ToolCall


def _fix_json_newlines(s: str) -> str:
    """
    Replace literal newline characters inside JSON string values with \\n.
    Many small models output tool-call JSON with unescaped newlines in code
    strings, making them invalid JSON.  This state-machine fixes that.
    """
    result: list[str] = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if in_string:
            if c == "\\":         # escape sequence — copy next char verbatim
                result.append(c)
                i += 1
                if i < len(s):
                    result.append(s[i])
                    i += 1
                continue
            elif c == '"':
                in_string = False
                result.append(c)
            elif c == "\n":      # illegal bare newline inside JSON string
                result.append("\\n")
            elif c == "\r":
                result.append("\\r")
            elif c == "\t":
                result.append("\\t")
            else:
                result.append(c)
        else:
            if c == '"':
                in_string = True
                result.append(c)
            else:
                result.append(c)
        i += 1
    return "".join(result)


def _parse_text_tool_calls(content: str, known_tools: list[str]) -> list[ToolCall]:
    """
    Fallback parser for models that output tool calls as JSON text.
    Uses raw_decode to find the *first* valid JSON value in the text
    (stops at the correct closing bracket rather than greedy regex).

    Handles formats:
      {"name": "tool", "parameters": {...}}
      {"name": "tool", "arguments": {...}}
      [{"name": "tool", "parameters": {...}}, ...]
    """
    if not content:
        return []

    # Sanitise literal newlines inside JSON strings before parsing
    sanitised = _fix_json_newlines(content)
    decoder = json.JSONDecoder()

    # Scan for the first { or [ and try to parse a full JSON value from there
    for i, ch in enumerate(sanitised):
        if ch not in ('{', '['):
            continue
        try:
            data, _ = decoder.raw_decode(sanitised, i)
        except json.JSONDecodeError:
            continue

        items = data if isinstance(data, list) else [data]
        calls: list[ToolCall] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("function") or item.get("tool")
            if not name or name not in known_tools:
                continue
            args = (
                item.get("parameters")
                or item.get("arguments")
                or item.get("args")
                or item.get("input")
                or {}
            )
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            calls.append(ToolCall(id=f"fallback_{uuid.uuid4().hex[:8]}", name=name, args=args))
        if calls:
            return calls

    return []


def _extract_code_block(content: str) -> ToolCall | None:
    """
    Last-resort fallback: if the model outputs a markdown code block
    (```python ... ```) treat it as a run_python call.
    This handles instruction-tuned models that reply with prose + code
    block instead of structured tool calls.
    """
    # Match ```python ... ``` or ``` ... ```
    # Only extract explicitly Python-tagged blocks to avoid running YAML/shell
    m = re.search(r"```python\s*\n([\s\S]+?)```", content)
    if m:
        code = m.group(1).strip()
        if code:
            return ToolCall(
                id=f"codeblock_{uuid.uuid4().hex[:8]}",
                name="run_python",
                args={"code": code},
            )
    return None


class OpenAICompatProvider(BaseLLMProvider):
    # Models with built-in chain-of-thought that is too slow on CPU.
    # We disable thinking for these to keep latency acceptable.
    _DISABLE_THINKING = ("qwen3",)

    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key or "ollama",
            base_url=base_url,
        )
        # Disable extended thinking for slow reasoning models
        self._no_think = any(m in model.lower() for m in self._DISABLE_THINKING)

    @staticmethod
    def _strip_think_tags(content: str | None) -> str | None:
        """Remove <think>...</think> blocks that leak into content."""
        if not content:
            return content
        import re
        stripped = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        return stripped or None

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        kwargs: dict = dict(model=self.model, messages=messages)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if self._no_think:
            kwargs["extra_body"] = {"think": False}

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message
        # Clean thinking tags from content before further processing
        msg.content = self._strip_think_tags(msg.content)  # type: ignore[assignment]

        tool_calls: list[ToolCall] = []

        # Native tool calls (proper function-calling models)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))

        # Fallback tiers for models that don't use native tool calling:
        elif choice.finish_reason == "stop" and msg.content and tools:
            known = [t["function"]["name"] for t in tools]

            # Tier 1: JSON-format tool call in the text (with newline sanitisation)
            tool_calls = _parse_text_tool_calls(msg.content, known)

            # Tier 2: markdown code block → run_python
            if not tool_calls and "run_python" in known:
                tc = _extract_code_block(msg.content)
                if tc:
                    tool_calls = [tc]

            if tool_calls:
                # Preserve any prose the model wrote as "thinking" by keeping
                # content; the agent loop emits it as a thinking event.
                pass  # content stays set; agent will show it as thinking

        return LLMResponse(content=msg.content, tool_calls=tool_calls)
