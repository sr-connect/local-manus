"""File system tools — all operations are sandboxed to the session workspace."""
from __future__ import annotations
from pathlib import Path
from .base import Tool, ToolResult


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file from the session workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file within the workspace.",
            }
        },
        "required": ["path"],
    }

    async def execute(self, path: str) -> ToolResult:
        try:
            target = self._safe_path(path)
            if not target.exists():
                return ToolResult(content=f"File not found: {path}", is_error=True)
            if not target.is_file():
                return ToolResult(content=f"Not a file: {path}", is_error=True)
            content = target.read_text(encoding="utf-8", errors="replace")
            return ToolResult(content=content or "(empty file)")
        except ValueError as exc:
            return ToolResult(content=str(exc), is_error=True)
        except Exception as exc:
            return ToolResult(content=f"Read error: {exc}", is_error=True)


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write text content to a file in the session workspace. "
        "Creates the file (and any missing parent directories) if it does not exist, "
        "or overwrites it if it does."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file within the workspace.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            target = self._safe_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(content=f"Written {len(content)} chars to {path}")
        except ValueError as exc:
            return ToolResult(content=str(exc), is_error=True)
        except Exception as exc:
            return ToolResult(content=f"Write error: {exc}", is_error=True)


class ListFilesTool(Tool):
    name = "list_files"
    description = "List files and directories in the session workspace (or a sub-directory)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Sub-directory to list. Defaults to workspace root ('.').",
                "default": ".",
            }
        },
        "required": [],
    }

    async def execute(self, path: str = ".") -> ToolResult:
        try:
            target = self._safe_path(path)
            if not target.exists():
                return ToolResult(content=f"Directory not found: {path}", is_error=True)
            entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
            lines = []
            for entry in entries:
                prefix = "📁 " if entry.is_dir() else "📄 "
                size = f"  ({entry.stat().st_size:,} bytes)" if entry.is_file() else ""
                lines.append(f"{prefix}{entry.name}{size}")
            return ToolResult(content="\n".join(lines) if lines else "(empty directory)")
        except ValueError as exc:
            return ToolResult(content=str(exc), is_error=True)
        except Exception as exc:
            return ToolResult(content=f"List error: {exc}", is_error=True)
