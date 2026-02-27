from .base import Tool, ToolResult
from .code_executor import PythonExecutorTool
from .shell import ShellTool
from .file_system import ReadFileTool, WriteFileTool, ListFilesTool
from .web_search import WebSearchTool

__all__ = [
    "Tool",
    "ToolResult",
    "PythonExecutorTool",
    "ShellTool",
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "WebSearchTool",
]


def get_all_tools(workspace):
    """Return a list of all available tool instances bound to a workspace."""
    return [
        PythonExecutorTool(workspace),
        ShellTool(workspace),
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        ListFilesTool(workspace),
        WebSearchTool(workspace),
    ]
