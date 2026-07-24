"""DataHub MCP context provider using Streamable HTTP."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from modelguard.context.base import DataHubContextError
from modelguard.context.normalise import (
    normalise_entity,
    normalise_lineage_results,
    utc_now_iso,
)
from modelguard.models import ContextSnapshot, LineageDirection

_REQUIRED_TOOLS = {"get_entities", "list_schema_fields", "get_lineage"}


class McpToolCaller(Protocol):
    """Minimal MCP transport contract used for testing and live connections."""

    def list_tools(self) -> set[str]:
        ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        ...


class StreamableHttpMcpToolCaller:
    """Synchronous wrapper around the official MCP Python client."""

    def __init__(self, *, server_url: str, token: str | None, timeout_seconds: float) -> None:
        self.server_url = server_url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def list_tools(self) -> set[str]:
        return set(self._run(self._list_tools()))

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._run(self._call_tool(name, arguments))

    def _run(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        raise DataHubContextError(
            "synchronous MCP calls cannot run inside an active event loop; use a worker thread"
        )

    async def _list_tools(self) -> list[str]:
        async with self._session() as session:
            response = await session.list_tools()
            return [tool.name for tool in response.tools]

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        async with self._session() as session:
            response = await session.call_tool(name, arguments=arguments)
            return _decode_tool_result(response)

    def _session(self) -> Any:
        return _McpSessionContext(
            server_url=self.server_url,
            token=self.token,
            timeout_seconds=self.timeout_seconds,
        )


class _McpSessionContext:
    def __init__(self, *, server_url: str, token: str | None, timeout_seconds: float) -> None:
        self.server_url = server_url
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._stack: Any = None

    async def __aenter__(self) -> Any:
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise DataHubContextError(
                'MCP support is not installed. Run: pip install -e ".[mcp]"'
            ) from exc

        from contextlib import AsyncExitStack

        self._stack = AsyncExitStack()
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        http_client = await self._stack.enter_async_context(
            httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        )
        read_stream, write_stream, _ = await self._stack.enter_async_context(
            streamable_http_client(self.server_url, http_client=http_client)
        )
        session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._stack is not None:
            await self._stack.aclose()


class DataHubMcpContextProvider:
    """Collect context using the DataHub MCP Server's read-only tools."""

    provider_name = "mcp"

    def __init__(
        self,
        *,
        tool_caller: McpToolCaller | None = None,
        server_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if tool_caller is None and not server_url:
            raise DataHubContextError("DataHub MCP URL is required")
        self.tool_caller = tool_caller or StreamableHttpMcpToolCaller(
            server_url=str(server_url),
            token=token,
            timeout_seconds=timeout_seconds,
        )

    def test_connection(self) -> None:
        try:
            tools = self.tool_caller.list_tools()
        except Exception as exc:
            raise DataHubContextError(f"DataHub MCP connection failed: {exc}") from exc
        missing = sorted(_REQUIRED_TOOLS - tools)
        if missing:
            raise DataHubContextError(
                f"DataHub MCP server is missing required tools: {missing}"
            )

    def collect(
        self,
        *,
        source_urn: str,
        source_column: str | None,
        direction: LineageDirection,
        max_hops: int,
        max_results: int,
        schema_limit: int,
    ) -> ContextSnapshot:
        try:
            entity_payload = self.tool_caller.call_tool(
                "get_entities", {"urns": source_urn}
            )
            schema_payload = self.tool_caller.call_tool(
                "list_schema_fields",
                {"urn": source_urn, "limit": schema_limit, "offset": 0},
            )
            upstream_payload: Any = []
            downstream_payload: Any = []
            if direction in {"upstream", "both"}:
                upstream_payload = self.tool_caller.call_tool(
                    "get_lineage",
                    {
                        "urn": source_urn,
                        "column": source_column,
                        "upstream": True,
                        "max_hops": max_hops,
                        "max_results": max_results,
                        "offset": 0,
                    },
                )
            if direction in {"downstream", "both"}:
                downstream_payload = self.tool_caller.call_tool(
                    "get_lineage",
                    {
                        "urn": source_urn,
                        "column": source_column,
                        "upstream": False,
                        "max_hops": max_hops,
                        "max_results": max_results,
                        "offset": 0,
                    },
                )
        except Exception as exc:
            if isinstance(exc, DataHubContextError):
                raise
            raise DataHubContextError(
                f"DataHub MCP context retrieval failed: {exc}"
            ) from exc

        return ContextSnapshot(
            source_urn=source_urn,
            provider="mcp",
            generated_at=utc_now_iso(),
            entity=normalise_entity(source_urn, entity_payload, schema_payload),
            upstream=normalise_lineage_results(upstream_payload, direction="upstream"),
            downstream=normalise_lineage_results(
                downstream_payload, direction="downstream"
            ),
            source_column=source_column,
            max_hops=max_hops,
            provider_metadata={
                "tools": sorted(_REQUIRED_TOOLS),
                "schema_limit": schema_limit,
                "max_results": max_results,
            },
        )


def _decode_tool_result(result: Any) -> Any:
    is_error = getattr(result, "isError", getattr(result, "is_error", False))
    if is_error:
        raise DataHubContextError(f"MCP tool returned an error: {result}")

    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured

    data = getattr(result, "data", None)
    if data is not None:
        return data

    text_values: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            text_values.append(str(text))
    if not text_values:
        return {}
    if len(text_values) == 1:
        try:
            return json.loads(text_values[0])
        except json.JSONDecodeError:
            return text_values[0]
    return text_values
