"""
Core agent — implements the ReAct loop (Reason → Act → Observe → repeat).

The agent is an async generator: each iteration yields an AgentEvent that
is streamed to the client via SSE so the user can watch progress live.
"""
from __future__ import annotations
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import AsyncIterator

from llm.base import BaseLLMProvider
from tools.base import Tool
import config


SYSTEM_PROMPT = """You are LocalManus. Use tools to complete tasks — always call a tool, never describe it.

Rules:
- Call run_python to execute Python code. Fix errors and retry.
- Call write_file / read_file for file operations.
- Call web_search for internet lookups.
- Give a plain text final answer only when the task is done.

Workspace: {workspace}
Python packages: pandas, numpy, matplotlib, requests."""


@dataclass
class AgentEvent:
    type: str  # thinking | tool_call | tool_result | message | error | done
    content: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_call_id: str | None = None
    is_error: bool = False

    def to_sse(self) -> str:
        return f"data: {json.dumps(asdict(self))}\n\n"


class Agent:
    """
    Single-agent ReAct executor.

    Usage:
        agent = Agent(llm, tools, workspace)
        async for event in agent.run("Analyse sales.csv and plot revenue by month"):
            send_sse(event)
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        tools: list[Tool],
        workspace: Path,
        max_iterations: int = config.MAX_ITERATIONS,
    ):
        self.llm = llm
        self.tools: dict[str, Tool] = {t.name: t for t in tools}
        self.workspace = workspace
        self.max_iterations = max_iterations
        self.messages: list[dict] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(workspace=str(workspace)),
            }
        ]

    def _tool_definitions(self) -> list[dict]:
        return [t.to_openai_dict() for t in self.tools.values()]

    # Common parameter aliases small models use instead of the correct names
    _PARAM_ALIASES: dict[str, str] = {
        "fp": "path", "filepath": "path", "filename": "path", "file": "path",
        "file_path": "path", "file_name": "path",
        "script": "code", "python_code": "code", "python": "code",
        "cmd": "command", "shell_command": "command", "bash": "command",
        "q": "query", "search_query": "query", "search": "query",
        "text": "content", "body": "content", "data": "content",
        "n": "num_results", "count": "num_results", "limit": "num_results",
    }

    def _normalise_args(self, args: dict) -> dict:
        """Rename known alias keys to their canonical parameter names."""
        return {self._PARAM_ALIASES.get(k, k): v for k, v in args.items()}

    async def _execute_tool(self, name: str, args: dict):
        tool = self.tools.get(name)
        if tool is None:
            from tools.base import ToolResult
            return ToolResult(content=f"Unknown tool: {name!r}", is_error=True)
        try:
            return await tool.execute(**self._normalise_args(args))
        except TypeError as exc:
            from tools.base import ToolResult
            return ToolResult(content=f"Invalid arguments for {name}: {exc}", is_error=True)
        except Exception as exc:
            from tools.base import ToolResult
            return ToolResult(content=f"Tool execution error: {exc}", is_error=True)

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]:
        self.messages.append({"role": "user", "content": user_message})

        for iteration in range(self.max_iterations):
            # ── LLM inference ──────────────────────────────────────────────
            try:
                response = await self.llm.chat(
                    messages=self.messages,
                    tools=self._tool_definitions(),
                )
            except Exception as exc:
                yield AgentEvent(type="error", content=f"LLM error: {exc}", is_error=True)
                yield AgentEvent(type="done")
                return

            # ── Final text response ─────────────────────────────────────────
            if response.is_final:
                self.messages.append(
                    {"role": "assistant", "content": response.content}
                )
                yield AgentEvent(type="message", content=response.content)
                yield AgentEvent(type="done")
                return

            # ── Tool calls ──────────────────────────────────────────────────
            # Emit any thinking text the model produced alongside tool calls
            if response.content:
                yield AgentEvent(type="thinking", content=response.content)

            # Record assistant turn with tool calls
            self.messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [tc.to_openai_dict() for tc in response.tool_calls],
                }
            )

            for tool_call in response.tool_calls:
                yield AgentEvent(
                    type="tool_call",
                    tool_name=tool_call.name,
                    tool_args=tool_call.args,
                    tool_call_id=tool_call.id,
                )

                result = await self._execute_tool(tool_call.name, tool_call.args)

                # Append a retry hint for errors so small models self-debug
                tool_content = result.content
                if result.is_error:
                    tool_content += "\n\nThe tool call failed. Fix the error and call the tool again."

                # Record tool result
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content,
                    }
                )

                yield AgentEvent(
                    type="tool_result",
                    content=result.content,
                    tool_call_id=tool_call.id,
                    is_error=result.is_error,
                )

        # Exhausted iterations
        yield AgentEvent(
            type="error",
            content=f"Reached the maximum of {self.max_iterations} iterations without finishing.",
            is_error=True,
        )
        yield AgentEvent(type="done")
