"""Execute shell commands inside the session workspace."""
from __future__ import annotations
import asyncio
from pathlib import Path
from .base import Tool, ToolResult

TIMEOUT = 30


class ShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell (bash) command in the session workspace directory. "
        "Use for file operations, running scripts, installing packages, etc. "
        "Avoid long-running processes; 30 second timeout enforced."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run.",
            }
        },
        "required": ["command"],
    }

    async def execute(self, command: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult(
                    content=f"Command timed out after {TIMEOUT}s.", is_error=True
                )

            out = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")
            combined = out
            if err:
                combined += f"\n--- stderr ---\n{err}"
            return ToolResult(
                content=combined.strip() or "(no output)",
                is_error=proc.returncode != 0,
            )
        except Exception as exc:
            return ToolResult(content=f"Shell error: {exc}", is_error=True)
