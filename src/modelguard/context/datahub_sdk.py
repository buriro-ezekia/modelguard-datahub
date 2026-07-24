"""DataHub Python SDK context provider."""

from __future__ import annotations

from typing import Any

from modelguard.context.base import DataHubContextError
from modelguard.context.normalise import (
    normalise_entity,
    normalise_lineage_results,
    to_primitive,
    utc_now_iso,
)
from modelguard.models import ContextSnapshot, LineageDirection


class DataHubSdkContextProvider:
    """Collect context using DataHub SDK v2 clients."""

    provider_name = "sdk"

    def __init__(
        self,
        *,
        client: Any | None = None,
        server: str | None = None,
        token: str | None = None,
    ) -> None:
        self.client = (
            client
            if client is not None
            else self._create_client(server=server, token=token)
        )

    def test_connection(self) -> None:
        try:
            self.client.test_connection()
        except Exception as exc:
            raise DataHubContextError(f"DataHub SDK connection failed: {exc}") from exc

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
        del schema_limit
        try:
            entity_payload = self.client.entities.get(source_urn)
            upstream_payload: Any = []
            downstream_payload: Any = []
            if direction in {"upstream", "both"}:
                upstream_payload = self.client.lineage.get_lineage(
                    source_urn=source_urn,
                    source_column=source_column,
                    direction="upstream",
                    max_hops=max_hops,
                    count=max_results,
                )
            if direction in {"downstream", "both"}:
                downstream_payload = self.client.lineage.get_lineage(
                    source_urn=source_urn,
                    source_column=source_column,
                    direction="downstream",
                    max_hops=max_hops,
                    count=max_results,
                )
        except Exception as exc:
            raise DataHubContextError(f"DataHub SDK context retrieval failed: {exc}") from exc

        return ContextSnapshot(
            source_urn=source_urn,
            provider="sdk",
            generated_at=utc_now_iso(),
            entity=normalise_entity(source_urn, entity_payload),
            upstream=normalise_lineage_results(upstream_payload, direction="upstream"),
            downstream=normalise_lineage_results(downstream_payload, direction="downstream"),
            source_column=source_column,
            max_hops=max_hops,
            provider_metadata={
                "sdk_entity_type": type(entity_payload).__name__,
                "raw_lineage_counts": {
                    "upstream": len(to_primitive(upstream_payload) or []),
                    "downstream": len(to_primitive(downstream_payload) or []),
                },
            },
        )

    @staticmethod
    def _create_client(*, server: str | None, token: str | None) -> Any:
        try:
            from datahub.sdk.main_client import DataHubClient
        except ImportError as exc:
            raise DataHubContextError(
                'DataHub SDK support is not installed. Run: pip install -e ".[datahub]"'
            ) from exc

        if server:
            return DataHubClient(server=server, token=token)
        try:
            return DataHubClient.from_env()
        except Exception as exc:
            raise DataHubContextError(
                "DataHub SDK credentials are missing. Set DATAHUB_GMS_URL and "
                "DATAHUB_GMS_TOKEN or run `datahub init`."
            ) from exc
