"""Provider-neutral context collection orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from modelguard.config import ModelGuardConfig
from modelguard.context.base import ContextProvider
from modelguard.models import ContextSnapshot, LineageDirection


@dataclass(slots=True)
class ContextCollector:
    """Coordinate connection checks and metadata evidence collection."""

    config: ModelGuardConfig
    provider: ContextProvider

    def check(self) -> None:
        self.provider.test_connection()

    def collect(
        self,
        *,
        source_urn: str | None = None,
        source_column: str | None = None,
        direction: LineageDirection = "both",
    ) -> ContextSnapshot:
        settings = self.config.datahub
        return self.provider.collect(
            source_urn=source_urn or self.config.model_urn,
            source_column=source_column,
            direction=direction,
            max_hops=settings.max_hops,
            max_results=settings.max_results,
            schema_limit=settings.schema_limit,
        )
