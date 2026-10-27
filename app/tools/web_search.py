"""
app/tools/web_search.py
=======================
DuckDuckGo web search tool.

Uses the ``duckduckgo-search`` library for real searches, but tests
should mock the internal ``_search`` method to avoid network calls.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import ToolUnavailableError
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class DuckDuckGoSearchTool(Tool):
    """Search the web using DuckDuckGo."""

    def __init__(self, max_results: int = 5, timeout_seconds: float = 30.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self._max_results = max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo and return top results."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        """Execute a DuckDuckGo text search.

        Returns:
            Formatted search results as a string.

        Raises:
            ToolUnavailableError: if the search service is unreachable.
        """
        query = args["query"]
        try:
            results = await self._search(query)
        except Exception as exc:
            logger.error("DuckDuckGo search failed: %s", exc)
            raise ToolUnavailableError(tool_name=self.name) from exc

        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            href = r.get("href", r.get("link", ""))
            body = r.get("body", r.get("snippet", ""))
            lines.append(f"{i}. {title}\n   URL: {href}\n   {body}")
        return "\n\n".join(lines)

    async def _search(self, query: str) -> list[dict[str, str]]:
        """Perform the actual DuckDuckGo search (mockable in tests).

        Uses synchronous ``duckduckgo_search`` wrapped in ``run_in_executor``.
        """
        import asyncio
        from functools import partial

        def _sync_search(q: str) -> list[dict[str, str]]:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                return list(ddgs.text(q, max_results=self._max_results))

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(_sync_search, query))
