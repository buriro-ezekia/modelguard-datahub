"""Evidence contracts and deterministic root-cause candidate generation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from modelguard.models import ContextSnapshot

EvidenceKind = Literal[
    "metric",
    "change",
    "schema",
    "lineage",
    "quality",
    "observation",
]
HypothesisCategory = Literal[
    "feature_transformation",
    "source_data_quality",
    "schema_contract",
    "upstream_dependency",
    "training_configuration",
    "unknown",
]
DiagnosisStatus = Literal["ranked", "inconclusive"]
ConfidenceLabel = Literal["high", "medium", "low"]


@dataclass(frozen=True, slots=True)
class ChangedFile:
    """One changed repository file supplied by the CI integration."""

    path: str
    status: str = "modified"
    additions: tuple[str, ...] = ()
    deletions: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ChangedFile:
        return cls(
            path=str(value.get("path") or value.get("file") or ""),
            status=str(value.get("status") or "modified"),
            additions=_strings(value.get("additions") or value.get("added_lines")),
            deletions=_strings(value.get("deletions") or value.get("removed_lines")),
            symbols=_strings(value.get("symbols")),
            fields=_strings(value.get("fields") or value.get("columns")),
            assets=_strings(value.get("assets")),
        )

    @property
    def searchable_text(self) -> str:
        values = (
            self.path,
            *self.additions,
            *self.deletions,
            *self.symbols,
            *self.fields,
            *self.assets,
        )
        return " ".join(values).lower()


@dataclass(frozen=True, slots=True)
class Observation:
    """A deterministic data, model or pipeline observation."""

    kind: str
    status: str
    summary: str
    field: str | None = None
    asset: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Observation:
        return cls(
            kind=str(value.get("kind") or value.get("type") or "observation"),
            status=str(value.get("status") or "unknown"),
            summary=str(value.get("summary") or value.get("message") or ""),
            field=_optional_string(value.get("field") or value.get("column")),
            asset=_optional_string(value.get("asset") or value.get("urn")),
            details=dict(value.get("details") or {}),
        )


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Repository changes and runtime observations associated with a regression."""

    repository: str
    commit_sha: str
    pull_request: int | None = None
    changed_files: tuple[ChangedFile, ...] = ()
    observations: tuple[Observation, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ChangeSet:
        pull_request = value.get("pull_request")
        return cls(
            repository=str(value.get("repository") or "unknown"),
            commit_sha=str(value.get("commit_sha") or value.get("commit") or "unknown"),
            pull_request=int(pull_request) if pull_request is not None else None,
            changed_files=tuple(
                ChangedFile.from_dict(item)
                for item in value.get("changed_files", value.get("changes", []))
                if isinstance(item, dict)
            ),
            observations=tuple(
                Observation.from_dict(item)
                for item in value.get("observations", [])
                if isinstance(item, dict)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One immutable fact used to support or challenge a hypothesis."""

    evidence_id: str
    kind: EvidenceKind
    summary: str
    source: str
    strength: float
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HypothesisDraft:
    """Unranked root-cause candidate with explicit scoring signals."""

    category: HypothesisCategory
    title: str
    affected_asset: str | None
    affected_fields: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    rationale: str
    recommended_next_checks: tuple[str, ...]
    scoring_signals: dict[str, float]


@dataclass(frozen=True, slots=True)
class RootCauseHypothesis:
    """Ranked, auditable root-cause hypothesis."""

    hypothesis_id: str
    rank: int
    category: HypothesisCategory
    title: str
    affected_asset: str | None
    affected_fields: tuple[str, ...]
    confidence: ConfidenceLabel
    score: float
    score_components: dict[str, float]
    evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    rationale: str
    recommended_next_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DiagnosisReport:
    """Complete Phase 3 output for one regression investigation."""

    diagnosis_id: str
    generated_at: str
    status: DiagnosisStatus
    source_urn: str
    repository: str
    commit_sha: str
    pull_request: int | None
    metric: str
    top_hypothesis_id: str | None
    hypotheses: tuple[RootCauseHypothesis, ...]
    evidence: tuple[EvidenceItem, ...]
    policy: dict[str, float]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceBuilder:
    """Build a stable evidence registry from Phase 1, Phase 2 and CI inputs."""

    def build(
        self,
        evaluation: dict[str, Any],
        context: ContextSnapshot,
        changes: ChangeSet,
    ) -> tuple[EvidenceItem, ...]:
        evidence: list[EvidenceItem] = []

        def add(
            kind: EvidenceKind,
            summary: str,
            source: str,
            strength: float,
            attributes: dict[str, Any],
        ) -> None:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"E{len(evidence) + 1:03d}",
                    kind=kind,
                    summary=summary,
                    source=source,
                    strength=round(max(0.0, min(1.0, strength)), 3),
                    attributes=attributes,
                )
            )

        metric = str(evaluation.get("metric") or "unknown_metric")
        status = str(evaluation.get("status") or "unknown")
        add(
            "metric",
            (
                f"{metric} changed from {evaluation.get('baseline')} to "
                f"{evaluation.get('candidate')} with status {status}."
            ),
            "phase1:evaluation",
            1.0 if status == "failed" else 0.6,
            dict(evaluation),
        )

        for changed in changes.changed_files:
            add(
                "change",
                f"{changed.status.title()} file {changed.path} at commit {changes.commit_sha}.",
                f"repository:{changed.path}",
                0.95,
                {
                    "path": changed.path,
                    "status": changed.status,
                    "additions": list(changed.additions),
                    "deletions": list(changed.deletions),
                    "symbols": list(changed.symbols),
                    "fields": list(changed.fields),
                    "assets": list(changed.assets),
                    "searchable_text": changed.searchable_text,
                },
            )

        for schema_field in context.entity.schema_fields:
            add(
                "schema",
                (
                    f"Schema field {schema_field.field_path} has type "
                    f"{schema_field.native_type or 'unknown'} and nullable="
                    f"{schema_field.nullable}."
                ),
                f"datahub:{context.source_urn}",
                0.65,
                asdict(schema_field),
            )

        for asset in (*context.upstream, *context.downstream):
            add(
                "lineage",
                (
                    f"{asset.name or asset.urn} is {asset.hops} hop(s) "
                    f"{asset.direction} of the investigated model."
                ),
                f"datahub:{asset.urn}",
                max(0.45, 0.85 - (asset.hops - 1) * 0.1),
                asdict(asset),
            )

        for signal in context.entity.quality_signals:
            add(
                "quality",
                str(signal.get("summary") or signal.get("message") or signal),
                f"datahub:{context.source_urn}",
                0.85 if str(signal.get("status")).lower() == "failed" else 0.65,
                dict(signal),
            )

        for observation in changes.observations:
            add(
                "observation",
                observation.summary,
                "ci:observation",
                0.95 if observation.status.lower() == "failed" else 0.75,
                {
                    "kind": observation.kind,
                    "status": observation.status,
                    "field": observation.field,
                    "asset": observation.asset,
                    "details": observation.details,
                },
            )

        return tuple(evidence)


class CandidateGenerator:
    """Generate supported competing hypotheses without using an LLM."""

    def generate(
        self,
        evidence: tuple[EvidenceItem, ...],
        context: ContextSnapshot,
    ) -> tuple[HypothesisDraft, ...]:
        metric_ids = _ids(evidence, "metric")
        change_items = _items(evidence, "change")
        schema_items = _items(evidence, "schema")
        lineage_items = _items(evidence, "lineage")
        observation_items = _items(evidence, "observation")
        quality_items = _items(evidence, "quality")

        changed_fields = _changed_fields(change_items)
        observed_fields = {
            str(item.attributes.get("field"))
            for item in observation_items
            if item.attributes.get("field")
        }
        affected_fields = tuple(sorted(changed_fields | observed_fields))
        nearest_transform = _nearest_transform_asset(lineage_items, changed_fields)

        drafts: list[HypothesisDraft] = []
        transformation_changes = tuple(
            item.evidence_id
            for item in change_items
            if _looks_like_transformation(item, changed_fields)
        )
        transformation_observations = tuple(
            item.evidence_id
            for item in observation_items
            if item.attributes.get("field") in changed_fields
            and item.attributes.get("status") in {"failed", "warning"}
        )
        transformation_lineage = tuple(
            item.evidence_id
            for item in lineage_items
            if _lineage_matches_fields(item, changed_fields)
            or item.attributes.get("platform") in {"dbt", "spark", "airflow"}
        )
        if transformation_changes:
            drafts.append(
                HypothesisDraft(
                    category="feature_transformation",
                    title="Changed feature transformation introduced invalid values",
                    affected_asset=nearest_transform,
                    affected_fields=affected_fields,
                    evidence_ids=_unique(
                        (*metric_ids, *transformation_changes, *transformation_lineage, *transformation_observations)
                    ),
                    counter_evidence_ids=(),
                    rationale=(
                        "A pull-request change touches model input fields on the DataHub lineage path, "
                        "and deterministic observations show an adverse candidate-data change."
                    ),
                    recommended_next_checks=(
                        "Reproduce the changed transformation on rows containing boundary values.",
                        "Compare baseline and candidate distributions for the affected fields.",
                        "Run the model evaluation after applying the smallest guarded transformation.",
                    ),
                    scoring_signals={
                        "temporal_proximity": 1.0,
                        "lineage_relevance": 1.0 if transformation_lineage else 0.45,
                        "metric_explanation": 1.0 if metric_ids else 0.0,
                        "quality_corroboration": 1.0 if transformation_observations else 0.25,
                        "specificity": 1.0 if affected_fields else 0.4,
                    },
                )
            )

        source_observations = tuple(
            item.evidence_id
            for item in observation_items
            if item.attributes.get("status") in {"failed", "warning"}
            and _looks_like_source_quality(item)
        )
        upstream_source = _furthest_upstream_asset(lineage_items)
        if source_observations or quality_items:
            drafts.append(
                HypothesisDraft(
                    category="source_data_quality",
                    title="Upstream source values caused the model regression",
                    affected_asset=upstream_source,
                    affected_fields=tuple(sorted(observed_fields)),
                    evidence_ids=_unique(
                        (*metric_ids, *source_observations, *_ids_from_items(quality_items), *_source_lineage_ids(lineage_items))
                    ),
                    counter_evidence_ids=transformation_changes,
                    rationale=(
                        "Boundary or invalid source values are present upstream, but a direct code "
                        "change may better explain why those values became harmful in this candidate."
                    ),
                    recommended_next_checks=(
                        "Compare source-field validity rates between baseline and candidate windows.",
                        "Confirm whether the same source values existed before the pull request.",
                    ),
                    scoring_signals={
                        "temporal_proximity": 0.35,
                        "lineage_relevance": 0.8 if upstream_source else 0.0,
                        "metric_explanation": 0.7 if metric_ids else 0.0,
                        "quality_corroboration": 0.9 if source_observations else 0.55,
                        "specificity": 0.75 if observed_fields else 0.35,
                    },
                )
            )

        schema_change_ids = tuple(
            item.evidence_id for item in change_items if _looks_like_schema_change(item)
        )
        schema_counter_ids = tuple(
            item.evidence_id for item in change_items if item.evidence_id not in schema_change_ids
        )
        if schema_items:
            drafts.append(
                HypothesisDraft(
                    category="schema_contract",
                    title="A schema or nullability contract changed",
                    affected_asset=context.source_urn,
                    affected_fields=tuple(
                        sorted(
                            str(item.attributes.get("field_path"))
                            for item in schema_items
                            if item.attributes.get("field_path")
                        )
                    ),
                    evidence_ids=_unique((*metric_ids, *schema_change_ids, *_ids_from_items(schema_items))),
                    counter_evidence_ids=schema_counter_ids,
                    rationale=(
                        "The model input schema is relevant, but the supplied change evidence does "
                        "not show a direct schema migration unless explicitly cited."
                    ),
                    recommended_next_checks=(
                        "Compare baseline and candidate DataHub schema aspects.",
                        "Inspect nullable and native-type changes for model input fields.",
                    ),
                    scoring_signals={
                        "temporal_proximity": 0.85 if schema_change_ids else 0.1,
                        "lineage_relevance": 0.55,
                        "metric_explanation": 0.45 if metric_ids else 0.0,
                        "quality_corroboration": 0.3,
                        "specificity": 0.45,
                    },
                )
            )

        upstream_change_ids = tuple(
            item.evidence_id
            for item in change_items
            if any(token in str(item.attributes.get("searchable_text", "")) for token in ("sql", "pipeline", "dependency", "source", "job"))
        )
        if upstream_change_ids:
            drafts.append(
                HypothesisDraft(
                    category="upstream_dependency",
                    title="An upstream pipeline or dependency changed",
                    affected_asset=_nearest_upstream_asset(lineage_items),
                    affected_fields=affected_fields,
                    evidence_ids=_unique((*metric_ids, *upstream_change_ids, *_ids_from_items(lineage_items))),
                    counter_evidence_ids=(),
                    rationale="Repository changes reference an upstream job or dependency on the model lineage path.",
                    recommended_next_checks=(
                        "Compare dependency versions and pipeline outputs with the approved baseline.",
                    ),
                    scoring_signals={
                        "temporal_proximity": 0.9,
                        "lineage_relevance": 0.85,
                        "metric_explanation": 0.55,
                        "quality_corroboration": 0.35,
                        "specificity": 0.55,
                    },
                )
            )

        if not drafts:
            drafts.append(
                HypothesisDraft(
                    category="unknown",
                    title="Insufficient evidence to identify a root cause",
                    affected_asset=context.source_urn,
                    affected_fields=(),
                    evidence_ids=metric_ids,
                    counter_evidence_ids=(),
                    rationale="The regression is known, but no causally specific evidence was supplied.",
                    recommended_next_checks=(
                        "Collect changed files, field-level observations and upstream quality results.",
                    ),
                    scoring_signals={
                        "temporal_proximity": 0.0,
                        "lineage_relevance": 0.2,
                        "metric_explanation": 0.3,
                        "quality_corroboration": 0.0,
                        "specificity": 0.0,
                    },
                )
            )

        return tuple(drafts)


def diagnosis_id(
    evaluation: dict[str, Any],
    context: ContextSnapshot,
    changes: ChangeSet,
) -> str:
    payload = {
        "evaluation": evaluation,
        "context": context.to_dict(),
        "changes": changes.to_dict(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"diag-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}"


def _items(evidence: tuple[EvidenceItem, ...], kind: EvidenceKind) -> tuple[EvidenceItem, ...]:
    return tuple(item for item in evidence if item.kind == kind)


def _ids(evidence: tuple[EvidenceItem, ...], kind: EvidenceKind) -> tuple[str, ...]:
    return tuple(item.evidence_id for item in evidence if item.kind == kind)


def _ids_from_items(items: tuple[EvidenceItem, ...]) -> tuple[str, ...]:
    return tuple(item.evidence_id for item in items)


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _changed_fields(items: tuple[EvidenceItem, ...]) -> set[str]:
    fields: set[str] = set()
    for item in items:
        fields.update(str(value) for value in item.attributes.get("fields", []) if value)
    return fields


def _looks_like_transformation(item: EvidenceItem, fields: set[str]) -> bool:
    text = str(item.attributes.get("searchable_text", ""))
    markers = ("feature", "transform", "calculate", "derive", "divide", "ratio", "spend")
    return any(marker in text for marker in markers) or any(field.lower() in text for field in fields)


def _looks_like_schema_change(item: EvidenceItem) -> bool:
    text = str(item.attributes.get("searchable_text", ""))
    return any(marker in text for marker in ("schema", "migration", "nullable", "cast", "dtype", "type"))


def _looks_like_source_quality(item: EvidenceItem) -> bool:
    text = f"{item.summary} {item.attributes}".lower()
    return any(
        marker in text
        for marker in ("zero", "null", "missing", "invalid", "outlier", "infinite", "nan", "drift")
    )


def _lineage_matches_fields(item: EvidenceItem, fields: set[str]) -> bool:
    text = json.dumps(item.attributes, sort_keys=True).lower()
    return any(field.lower() in text for field in fields)


def _nearest_transform_asset(items: tuple[EvidenceItem, ...], fields: set[str]) -> str | None:
    matching = [
        item
        for item in items
        if item.attributes.get("direction") == "upstream"
        and (
            _lineage_matches_fields(item, fields)
            or item.attributes.get("platform") in {"dbt", "spark"}
        )
    ]
    return _asset_urn(min(matching, key=_hops)) if matching else _nearest_upstream_asset(items)


def _nearest_upstream_asset(items: tuple[EvidenceItem, ...]) -> str | None:
    upstream = [item for item in items if item.attributes.get("direction") == "upstream"]
    return _asset_urn(min(upstream, key=_hops)) if upstream else None


def _furthest_upstream_asset(items: tuple[EvidenceItem, ...]) -> str | None:
    upstream = [item for item in items if item.attributes.get("direction") == "upstream"]
    return _asset_urn(max(upstream, key=_hops)) if upstream else None


def _source_lineage_ids(items: tuple[EvidenceItem, ...]) -> tuple[str, ...]:
    upstream = [item for item in items if item.attributes.get("direction") == "upstream"]
    if not upstream:
        return ()
    furthest_hops = max(_hops(item) for item in upstream)
    return tuple(item.evidence_id for item in upstream if _hops(item) == furthest_hops)


def _asset_urn(item: EvidenceItem) -> str | None:
    return _optional_string(item.attributes.get("urn"))


def _hops(item: EvidenceItem) -> int:
    return int(item.attributes.get("hops") or 1)


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        value = [value]
    return tuple(str(item) for item in value if item is not None)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def field_tokens(value: str) -> set[str]:
    """Return normalised tokens for future semantic field matching."""
    return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}
