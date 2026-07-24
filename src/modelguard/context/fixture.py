"""Deterministic fixture-backed context provider for CI and demonstrations."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.context.base import DataHubContextError
from modelguard.models import ContextSnapshot, LineageDirection


class FixtureContextProvider:
    provider_name = "fixture"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path)

    def test_connection(self) -> None:
        if not self.fixture_path.is_file():
            raise DataHubContextError(f"fixture file not found: {self.fixture_path}")
        self._load()

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
        del max_results, schema_limit
        snapshot = self._load()
        if source_urn != snapshot.source_urn:
            raise DataHubContextError(
                "fixture source URN mismatch: "
                f"requested {source_urn}, fixture has {snapshot.source_urn}"
            )

        upstream = snapshot.upstream if direction in {"upstream", "both"} else ()
        downstream = snapshot.downstream if direction in {"downstream", "both"} else ()
        return ContextSnapshot(
            source_urn=snapshot.source_urn,
            provider="fixture",
            generated_at=snapshot.generated_at,
            entity=snapshot.entity,
            upstream=tuple(item for item in upstream if item.hops <= max_hops),
            downstream=tuple(item for item in downstream if item.hops <= max_hops),
            source_column=source_column,
            max_hops=max_hops,
            provider_metadata={
                **snapshot.provider_metadata,
                "fixture_name": self.fixture_path.name,
            },
        )

    def _load(self) -> ContextSnapshot:
        try:
            payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataHubContextError(f"invalid context fixture: {exc}") from exc
        if not isinstance(payload, dict):
            raise DataHubContextError("context fixture root must be a JSON object")
        return ContextSnapshot.from_dict(payload)
