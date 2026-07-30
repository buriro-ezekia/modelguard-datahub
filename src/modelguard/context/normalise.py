"""Normalisation helpers for DataHub SDK and MCP payloads."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from modelguard.models import EntityContext, LineageAssetContext, SchemaFieldContext

_PUBLIC_ATTRIBUTES = (
    "urn",
    "entity_type",
    "type",
    "name",
    "display_name",
    "displayName",
    "qualified_name",
    "platform",
    "description",
    "owners",
    "ownership",
    "tags",
    "terms",
    "glossary_terms",
    "glossaryTerms",
    "schema",
    "schema_fields",
    "schemaMetadata",
    "fields",
    "field_path",
    "fieldPath",
    "native_type",
    "nativeDataType",
    "nullable",
    "quality_signals",
    "assertions",
    "incidents",
    "custom_properties",
    "customProperties",
    "model_group",
    "groups",
    "deployments",
    "hyper_params",
    "training_metrics",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def to_primitive(value: Any) -> Any:
    """Convert SDK, Pydantic and dataclass objects into JSON-compatible values."""

    return _to_primitive(value, seen=set())


def _to_primitive(value: Any, *, seen: set[int]) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value

    identity = id(value)
    if identity in seen:
        return str(value)

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        seen.add(identity)
        try:
            return {
                key: _to_primitive(item, seen=seen)
                for key, item in dataclasses.asdict(value).items()
            }
        finally:
            seen.discard(identity)

    if isinstance(value, Mapping):
        seen.add(identity)
        try:
            return {
                str(key): _to_primitive(item, seen=seen) for key, item in value.items()
            }
        finally:
            seen.discard(identity)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        seen.add(identity)
        try:
            return [_to_primitive(item, seen=seen) for item in value]
        finally:
            seen.discard(identity)

    if hasattr(value, "model_dump"):
        try:
            return _to_primitive(
                value.model_dump(by_alias=True, exclude_none=True),
                seen=seen,
            )
        except (AttributeError, TypeError, ValueError):
            pass

    if hasattr(value, "to_obj"):
        try:
            return _to_primitive(value.to_obj(), seen=seen)
        except (AttributeError, TypeError, ValueError):
            pass

    projected = _project_public_attributes(value, seen=seen)
    if projected:
        return projected

    return str(value)


def _project_public_attributes(value: Any, *, seen: set[int]) -> dict[str, Any]:
    """Extract safe public values from SDK objects that use slots or properties."""

    identity = id(value)
    if identity in seen:
        return {}
    seen.add(identity)
    try:
        output: dict[str, Any] = {}
        raw_values = vars(value) if hasattr(value, "__dict__") else {}
        for key, item in raw_values.items():
            if not str(key).startswith("_") and not callable(item):
                output[str(key)] = _to_primitive(item, seen=seen)

        for attribute in _PUBLIC_ATTRIBUTES:
            if attribute in output:
                continue
            try:
                item = getattr(value, attribute)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            if callable(item):
                continue
            output[attribute] = _to_primitive(item, seen=seen)
        return output
    finally:
        seen.discard(identity)


def normalise_entity(
    source_urn: str,
    entity_payload: Any,
    schema_payload: Any | None = None,
) -> EntityContext:
    raw = to_primitive(entity_payload)
    if not isinstance(raw, dict):
        raw = {"urn": source_urn, "value": raw}
    raw = _canonicalise_entity(raw, source_urn=source_urn)

    schema_raw = to_primitive(schema_payload)
    if isinstance(schema_raw, dict) and isinstance(schema_raw.get("fields"), list):
        raw = dict(raw)
        raw["schema_fields"] = schema_raw["fields"]

    return EntityContext.from_dict(raw, urn=source_urn)


def _canonicalise_entity(raw: dict[str, Any], *, source_urn: str) -> dict[str, Any]:
    output = dict(raw)
    resolved_urn = str(output.get("urn") or source_urn)
    output["urn"] = resolved_urn

    aliases = {
        "display_name": "displayName",
        "qualified_name": "name",
        "entity_type": "entityType",
        "glossary_terms": "glossaryTerms",
        "custom_properties": "customProperties",
        "quality_signals": "qualitySignals",
    }
    for source, target in aliases.items():
        if output.get(target) is None and output.get(source) is not None:
            output[target] = output[source]

    schema = output.get("schema")
    if not output.get("schema_fields") and isinstance(schema, dict):
        fields = schema.get("fields") or schema.get("schema_fields")
        if isinstance(fields, list):
            output["schema_fields"] = fields
    if not output.get("schema_fields") and isinstance(output.get("fields"), list):
        output["schema_fields"] = output["fields"]

    if output.get("glossaryTerms") is None and output.get("terms") is not None:
        output["glossaryTerms"] = output["terms"]

    identity = _urn_identity(resolved_urn)
    if not output.get("entityType") and not output.get("type"):
        output["entityType"] = identity["entity_type"]
    if not output.get("platform"):
        output["platform"] = identity["platform"]
    if not output.get("name") and not output.get("displayName"):
        output["name"] = identity["name"]
    return output


def _urn_identity(urn: str) -> dict[str, str | None]:
    entity_match = re.match(r"^urn:li:([^:]+):", urn)
    entity_type = entity_match.group(1).upper() if entity_match else None

    platform_match = re.search(r"urn:li:dataPlatform:([^,)]+)", urn)
    platform = platform_match.group(1) if platform_match else None

    name: str | None = None
    tuple_match = re.match(
        r"^urn:li:[^:]+:\(urn:li:dataPlatform:[^,]+,(.*),[^,)]+\)$",
        urn,
    )
    if tuple_match:
        name = tuple_match.group(1)
    elif urn.startswith("urn:li:mlFeature:(") or urn.startswith("urn:li:mlPrimaryKey:("):
        inner = urn.split(":(", 1)[1].removesuffix(")")
        name = inner.rsplit(",", 1)[-1]
    return {"entity_type": entity_type, "platform": platform, "name": name}


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
    if isinstance(candidate, dict):
        nested = candidate.get("searchResults") or candidate.get("results")
        if isinstance(nested, list):
            return nested

    results = raw.get("searchResults") or raw.get("results")
    return results if isinstance(results, list) else []
