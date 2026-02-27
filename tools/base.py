"""Base classes for all tools."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


class Tool(ABC):
    """Each tool has a name, description, JSON Schema parameters, and execute()."""

    name: str
    description: str
    parameters: dict  # JSON Schema object

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    def to_openai_dict(self) -> dict:
        """OpenAI / Ollama function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def _safe_path(self, path: str) -> Path:
        """Resolve path within the workspace; raise if it escapes."""
        resolved = (self.workspace / path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            raise ValueError(f"Path '{path}' escapes the workspace. Access denied.")
        return resolved
