"""Web search via DuckDuckGo (no API key required)."""
from __future__ import annotations
from pathlib import Path
from .base import Tool, ToolResult


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web using DuckDuckGo. Returns titles, URLs, and snippets. "
        "No API key required. Use for finding current information, documentation, "
        "news, or anything that requires accessing the internet."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:
        num_results = min(int(num_results), 10)
        try:
            try:
                from ddgs import DDGS  # new package name
            except ImportError:
                from duckduckgo_search import DDGS  # legacy name fallback

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(r)

            if not results:
                return ToolResult(content="No results found.")

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(
                    f"[{i}] {r.get('title', 'No title')}\n"
                    f"    URL: {r.get('href', '')}\n"
                    f"    {r.get('body', '')}"
                )
            return ToolResult(content="\n\n".join(lines))

        except ImportError:
            return ToolResult(
                content="duckduckgo-search not installed. Run: pip install duckduckgo-search",
                is_error=True,
            )
        except Exception as exc:
            return ToolResult(content=f"Search error: {exc}", is_error=True)
