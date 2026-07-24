"""Typed, provider-neutral metadata context models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ContextProviderName = Literal["fixture", "sdk", "mcp"]
LineageDirection = Literal["upstream", "downstream", "both"]


@dataclass(frozen=True, slots=True)
class SchemaFieldContext:
    """Normalised schema-field evidence."""

    field_path: str
    native_type: str | None = None
    description: str | None = None
    nullable: bool | None = None
    tags: tuple[str, ...] = ()
    glossary_terms: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SchemaFieldContext:
        return cls(
            field_path=str(
                value.get("field_path")
                or value.get("fieldPath")
                or value.get("name")
                or ""
            ),
            native_type=_optional_string(
                value.get("native_type")
                or value.get("nativeDataType")
                or value.get("type")
            ),
            description=_optional_string(value.get("description")),
            nullable=_optional_bool(value.get("nullable")),
            tags=tuple(_string_list(value.get("tags"))),
            glossary_terms=tuple(
                _string_list(value.get("glossary_terms") or value.get("glossaryTerms"))
            ),
        )


@dataclass(frozen=True, slots=True)
class LineageAssetContext:
    """Normalised upstream or downstream lineage evidence."""

    urn: str
    direction: Literal["upstream", "downstream"]
    hops: int = 1
    entity_type: str | None = None
    name: str | None = None
    platform: str | None = None
    description: str | None = None
    paths: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        direction: Literal["upstream", "downstream"],
    ) -> LineageAssetContext:
        entity = value.get("entity") if isinstance(value.get("entity"), dict) else {}
        urn = value.get("urn") or entity.get("urn")
        raw_paths = value.get("paths") or []
        paths: list[tuple[str, ...]] = []
        for raw_path in raw_paths:
            if isinstance(raw_path, list):
                paths.append(tuple(_path_urn(item) for item in raw_path))
        return cls(
            urn=str(urn or ""),
            direction=direction,
            hops=int(value.get("hops") or value.get("degree") or 1),
            entity_type=_optional_string(value.get("type") or entity.get("type")),
            name=_optional_string(value.get("name") or entity.get("name")),
            platform=_optional_string(value.get("platform") or entity.get("platform")),
            description=_optional_string(
                value.get("description") or entity.get("description")
            ),
            paths=tuple(paths),
        )


@dataclass(frozen=True, slots=True)
class EntityContext:
    """Normalised metadata for the investigated source entity."""

    urn: str
    entity_type: str | None = None
    name: str | None = None
    platform: str | None = None
    description: str | None = None
    owners: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    glossary_terms: tuple[str, ...] = ()
    schema_fields: tuple[SchemaFieldContext, ...] = ()
    quality_signals: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, urn: str | None = None) -> EntityContext:
        resolved_urn = str(value.get("urn") or urn or "")
        schema_fields = _extract_schema_fields(value)
        return cls(
            urn=resolved_urn,
            entity_type=_optional_string(
                value.get("type") or value.get("entityType") or value.get("entity_type")
            ),
            name=_optional_string(value.get("name") or value.get("displayName")),
            platform=_platform_name(value.get("platform")),
            description=_description(value),
            owners=tuple(_extract_urns(value.get("owners") or value.get("ownership"))),
            tags=tuple(_extract_urns(value.get("tags") or value.get("globalTags"))),
            glossary_terms=tuple(
                _extract_urns(value.get("glossaryTerms") or value.get("glossary_terms"))
            ),
            schema_fields=tuple(schema_fields),
            quality_signals=tuple(_extract_quality_signals(value)),
            raw=dict(value.get("raw")) if isinstance(value.get("raw"), dict) else value,
        )


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Complete metadata evidence collected for one source asset."""

    source_urn: str
    provider: ContextProviderName
    generated_at: str
    entity: EntityContext
    upstream: tuple[LineageAssetContext, ...] = ()
    downstream: tuple[LineageAssetContext, ...] = ()
    source_column: str | None = None
    max_hops: int = 1
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContextSnapshot:
        entity_value = value.get("entity") or {"urn": value["source_urn"]}
        return cls(
            source_urn=str(value["source_urn"]),
            provider=value.get("provider", "fixture"),
            generated_at=str(value.get("generated_at") or "1970-01-01T00:00:00+00:00"),
            source_column=_optional_string(value.get("source_column")),
            max_hops=int(value.get("max_hops", 1)),
            entity=EntityContext.from_dict(entity_value, urn=str(value["source_urn"])),
            upstream=tuple(
                LineageAssetContext.from_dict(item, direction="upstream")
                for item in value.get("upstream", [])
            ),
            downstream=tuple(
                LineageAssetContext.from_dict(item, direction="downstream")
                for item in value.get("downstream", [])
            ),
            provider_metadata=dict(value.get("provider_metadata") or {}),
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, dict):
        value = value.get("elements") or value.get("values") or [value]
    if not isinstance(value, list):
        value = [value]
    output: list[str] = []
    for item in value:
        if isinstance(item, dict):
            candidate = (
                item.get("urn")
                or item.get("tag")
                or item.get("term")
                or item.get("name")
            )
        else:
            candidate = item
        if candidate is not None:
            output.append(str(candidate))
    return output


def _extract_urns(value: Any) -> list[str]:
    return _string_list(value)


def _platform_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return _optional_string(
            value.get("name") or value.get("urn") or value.get("platform")
        )
    return _optional_string(value)


def _description(value: dict[str, Any]) -> str | None:
    direct = value.get("description")
    if direct is not None:
        return _optional_string(direct)
    properties = value.get("properties") or value.get("datasetProperties") or {}
    if isinstance(properties, dict):
        return _optional_string(properties.get("description"))
    return None


def _extract_schema_fields(value: dict[str, Any]) -> list[SchemaFieldContext]:
    candidates: list[Any] = []
    for key in ("schema_fields", "schemaFields", "fields"):
        if isinstance(value.get(key), (list, tuple)):
            candidates = list(value[key])
            break
    if not candidates:
        schema = value.get("schemaMetadata") or value.get("schema_metadata") or {}
        if isinstance(schema, dict) and isinstance(schema.get("fields"), (list, tuple)):
            candidates = list(schema["fields"])
    return [
        SchemaFieldContext.from_dict(item)
        for item in candidates
        if isinstance(item, dict)
    ]


def _extract_quality_signals(value: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("quality_signals", "qualitySignals", "assertions", "incidents"):
        candidate = value.get(key)
        if isinstance(candidate, (list, tuple)):
            return [dict(item) for item in candidate if isinstance(item, dict)]
    return []


def _path_urn(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("urn")
            or value.get("fieldPath")
            or value.get("column_name")
            or value
        )
    return str(value)
