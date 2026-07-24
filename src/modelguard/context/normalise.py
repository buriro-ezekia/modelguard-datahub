"""Normalisation helpers for DataHub SDK and MCP payloads."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from modelguard.models import EntityContext, LineageAssetContext, SchemaFieldContext


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_primitive(value: Any) -> Any:
    """Convert SDK, Pydantic and dataclass objects into JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {key: to_primitive(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_primitive(item) for item in value]
    if hasattr(value, "model_dump"):
        return to_primitive(value.model_dump(by_alias=True, exclude_none=True))
    if hasattr(value, "to_obj"):
        return to_primitive(value.to_obj())
    if hasattr(value, "__dict__"):
        return {
            str(key): to_primitive(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def normalise_entity(
    source_urn: str,
    entity_payload: Any,
    schema_payload: Any | None = None,
) -> EntityContext:
    raw = to_primitive(entity_payload)
    if not isinstance(raw, dict):
        raw = {"urn": source_urn, "value": raw}

    schema_raw = to_primitive(schema_payload)
    if isinstance(schema_raw, dict) and isinstance(schema_raw.get("fields"), list):
        raw = dict(raw)
        raw["schema_fields"] = schema_raw["fields"]

    return EntityContext.from_dict(raw, urn=source_urn)


def normalise_lineage_results(
    payload: Any,
    *,
    direction: Literal["upstream", "downstream"],
) -> tuple[LineageAssetContext, ...]:
    raw = to_primitive(payload)
    items = _lineage_items(raw, direction)
    output: list[LineageAssetContext] = []
    for item in items:
        if not isinstance(item, dict):
            item = {"urn": str(item)}
        normalised = LineageAssetContext.from_dict(item, direction=direction)
        if normalised.urn:
            output.append(normalised)
    return tuple(output)


def normalise_schema_fields(payload: Any) -> tuple[SchemaFieldContext, ...]:
    raw = to_primitive(payload)
    fields = raw.get("fields", []) if isinstance(raw, dict) else raw
    if not isinstance(fields, list):
        return ()
    return tuple(
        SchemaFieldContext.from_dict(item) for item in fields if isinstance(item, dict)
    )


def _lineage_items(raw: Any, direction: str) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    key = "upstreams" if direction == "upstream" else "downstreams"
    candidate = raw.get(key)
    if isinstance(candidate, list):
        return candidate
    results = raw.get("searchResults") or raw.get("results")
    return results if isinstance(results, list) else []
