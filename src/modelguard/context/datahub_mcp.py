"""DataHub MCP context provider using Streamable HTTP."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

from modelguard.context.base import DataHubContextError
from modelguard.context.normalise import (
    normalise_entity,
    normalise_lineage_results,
    to_primitive,
    utc_now_iso,
)
from modelguard.models import ContextSnapshot, LineageDirection

_REQUIRED_TOOLS = {"get_entities", "list_schema_fields", "get_lineage"}
_URN_START = re.compile(r"urn:li:[A-Za-z0-9_]+:")


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
        session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
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
            raise DataHubContextError(f"DataHub MCP server is missing required tools: {missing}")

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
            entity_payload = _unwrap_tool_payload(
                self.tool_caller.call_tool("get_entities", {"urns": source_urn})
            )
            schema_payload = _unwrap_tool_payload(
                self.tool_caller.call_tool(
                    "list_schema_fields",
                    {"urn": source_urn, "limit": schema_limit, "offset": 0},
                )
            )
            upstream_payload: Any = []
            downstream_payload: Any = []
            if direction in {"upstream", "both"}:
                upstream_payload = _unwrap_tool_payload(
                    self.tool_caller.call_tool(
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
                )
            if direction in {"downstream", "both"}:
                downstream_payload = _unwrap_tool_payload(
                    self.tool_caller.call_tool(
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
                )
        except Exception as exc:
            if isinstance(exc, DataHubContextError):
                raise
            raise DataHubContextError(f"DataHub MCP context retrieval failed: {exc}") from exc

        return ContextSnapshot(
            source_urn=source_urn,
            provider="mcp",
            generated_at=utc_now_iso(),
            entity=normalise_entity(source_urn, entity_payload, schema_payload),
            upstream=normalise_lineage_results(upstream_payload, direction="upstream"),
            downstream=normalise_lineage_results(downstream_payload, direction="downstream"),
            source_column=source_column,
            max_hops=max_hops,
            provider_metadata={
                "tools": sorted(_REQUIRED_TOOLS),
                "schema_limit": schema_limit,
                "max_results": max_results,
                "entity_urns": sorted(_extract_urns(entity_payload)),
                "upstream_urns": sorted(_extract_urns(upstream_payload)),
                "downstream_urns": sorted(_extract_urns(downstream_payload)),
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
        return _unwrap_tool_payload(structured)

    data = getattr(result, "data", None)
    if data is not None:
        return _unwrap_tool_payload(data)

    text_values: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            text_values.append(str(text))
    if not text_values:
        return {}
    if len(text_values) == 1:
        return _unwrap_tool_payload(text_values[0])
    return [_unwrap_tool_payload(item) for item in text_values]


def _unwrap_tool_payload(value: Any) -> Any:
    """Unwrap FastMCP result envelopes and JSON-encoded tool payloads."""

    current = value
    for _ in range(4):
        if isinstance(current, str):
            stripped = current.strip()
            if stripped.startswith(("{", "[")):
                try:
                    current = json.loads(stripped)
                    continue
                except json.JSONDecodeError:
                    return current
            return current
        if isinstance(current, dict) and set(current) == {"result"}:
            current = current["result"]
            continue
        return current
    return current


def _extract_urns(value: Any) -> set[str]:
    """Extract exact DataHub URNs from nested or string-encoded MCP responses."""

    primitive = _unwrap_tool_payload(to_primitive(value))
    urns: set[str] = set()

    def visit(item: Any) -> None:
        item = _unwrap_tool_payload(item)
        if isinstance(item, dict):
            for key, nested in item.items():
                if str(key).lower().endswith("urn") and isinstance(nested, str):
                    urns.update(_urns_in_text(nested))
                visit(nested)
            return
        if isinstance(item, (list, tuple, set)):
            for nested in item:
                visit(nested)
            return
        if isinstance(item, str):
            urns.update(_urns_in_text(item))

    visit(primitive)
    return urns


def _urns_in_text(text: str) -> set[str]:
    output: set[str] = set()
    for match in _URN_START.finditer(text):
        start = match.start()
        cursor = match.end()
        if cursor < len(text) and text[cursor] == "(":
            depth = 0
            while cursor < len(text):
                character = text[cursor]
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0:
                        cursor += 1
                        break
                cursor += 1
        else:
            while cursor < len(text) and text[cursor] not in "\t\r\n \"'<>[]{}":
                cursor += 1
        candidate = text[start:cursor].rstrip(",.;")
        if candidate.startswith("urn:li:"):
            output.add(candidate)
    return output
