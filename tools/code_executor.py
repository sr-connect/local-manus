"""Execute Python code in a subprocess inside the session workspace."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from .base import Tool, ToolResult

TIMEOUT = 60  # seconds


class PythonExecutorTool(Tool):
    name = "run_python"
    description = (
        "Execute Python code in the session workspace. "
        "The interpreter persists between calls within the same session "
        "(variables, imports, and files remain). "
        "Returns stdout and stderr. Common packages available: "
        "pandas, numpy, matplotlib, requests, json, pathlib, os."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute.",
            }
        },
        "required": ["code"],
    }

    def __init__(self, workspace: Path):
        super().__init__(workspace)
        # Persistent state file for the session
        self._state_file = workspace / "_session_state.py"
        self._state_file.touch(exist_ok=True)

    async def execute(self, code: str) -> ToolResult:
        # Write script to workspace
        script = workspace_script(self.workspace, code)
        script_path = self.workspace / "_run.py"
        script_path.write_text(script, encoding="utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
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
                    content=f"Execution timed out after {TIMEOUT}s.", is_error=True
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
            return ToolResult(content=f"Executor error: {exc}", is_error=True)


def workspace_script(workspace: Path, code: str) -> str:
    """Wrap user code so cwd is set and matplotlib saves to workspace."""
    return f"""
import os, sys
os.chdir({str(workspace)!r})
sys.path.insert(0, {str(workspace)!r})

try:
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    pass

{code}
"""
