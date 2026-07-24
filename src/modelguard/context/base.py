"""Provider interfaces and common context errors."""

from __future__ import annotations

from typing import Protocol

from modelguard.models import ContextSnapshot, LineageDirection


class DataHubContextError(RuntimeError):
    """Raised when context cannot be retrieved or normalised safely."""


class ContextProvider(Protocol):
    """Contract implemented by all DataHub context providers."""

    provider_name: str

    def test_connection(self) -> None:
        """Verify that the provider is usable."""

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
        """Collect a complete provider-neutral context snapshot."""
