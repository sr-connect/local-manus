"""Abstract base classes for LLM providers."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]

    def to_openai_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.args),
            },
        }


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def is_final(self) -> bool:
        return not self.has_tool_calls


class BaseLLMProvider(ABC):
    """All providers implement this interface."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """Send messages and available tools; return response."""
        ...

    def tools_to_provider_format(self, tools: list[dict]) -> list[dict]:
        """Override in subclasses that need a different tool format."""
        return tools
