"""Context-provider construction from validated settings."""

from __future__ import annotations

from modelguard.config import DataHubSettings
from modelguard.context.base import ContextProvider, DataHubContextError
from modelguard.context.datahub_mcp import DataHubMcpContextProvider
from modelguard.context.datahub_sdk import DataHubSdkContextProvider
from modelguard.context.fixture import FixtureContextProvider


def build_context_provider(settings: DataHubSettings) -> ContextProvider:
    """Build the configured provider without logging or exposing secrets."""
    if settings.provider == "fixture":
        return FixtureContextProvider(settings.fixture_path)
    if settings.provider == "sdk":
        return DataHubSdkContextProvider(server=settings.gms_url, token=settings.token())
    if settings.provider == "mcp":
        if not settings.mcp_url:
            raise DataHubContextError(
                "DataHub MCP URL is missing. Set DATAHUB_MCP_URL or datahub.mcp_url."
            )
        return DataHubMcpContextProvider(
            server_url=settings.mcp_url,
            token=settings.mcp_token(),
            timeout_seconds=settings.timeout_seconds,
        )
    raise DataHubContextError(f"unsupported context provider: {settings.provider}")
