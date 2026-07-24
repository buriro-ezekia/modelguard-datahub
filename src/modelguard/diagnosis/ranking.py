"""Transparent scoring and abstention policy for root-cause hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from modelguard.diagnosis.hypotheses import (
    DiagnosisStatus,
    EvidenceItem,
    HypothesisDraft,
    RootCauseHypothesis,
)


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    """Weights and thresholds used by the deterministic ranker."""

    min_confidence: float = 0.45
    min_margin: float = 0.08
    temporal_weight: float = 0.25
    lineage_weight: float = 0.25
    metric_weight: float = 0.20
    quality_weight: float = 0.20
    specificity_weight: float = 0.10
    counter_evidence_penalty: float = 0.08
    low_diversity_penalty: float = 0.12

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if value < 0 or value > 1:
                raise ValueError(f"{name} must be between 0 and 1")
        weight_total = (
            self.temporal_weight
            + self.lineage_weight
            + self.metric_weight
            + self.quality_weight
            + self.specificity_weight
        )
        if abs(weight_total - 1.0) > 1e-9:
            raise ValueError("ranking weights must sum to 1.0")

    def to_dict(self) -> dict[str, float]:
        return {
            "min_confidence": self.min_confidence,
            "min_margin": self.min_margin,
            "temporal_weight": self.temporal_weight,
            "lineage_weight": self.lineage_weight,
            "metric_weight": self.metric_weight,
            "quality_weight": self.quality_weight,
            "specificity_weight": self.specificity_weight,
            "counter_evidence_penalty": self.counter_evidence_penalty,
            "low_diversity_penalty": self.low_diversity_penalty,
        }


@dataclass(frozen=True, slots=True)
class RankingResult:
    status: DiagnosisStatus
    hypotheses: tuple[RootCauseHypothesis, ...]
    top_hypothesis_id: str | None
    warnings: tuple[str, ...]


def rank_hypotheses(
    drafts: tuple[HypothesisDraft, ...],
    evidence: tuple[EvidenceItem, ...],
    policy: RankingPolicy,
) -> RankingResult:
    """Rank candidates and abstain when confidence or separation is insufficient."""
    evidence_by_id = {item.evidence_id: item for item in evidence}
    scored: list[tuple[HypothesisDraft, float, dict[str, float]]] = []
    for draft in drafts:
        components = _score_components(draft, evidence_by_id, policy)
        score = round(
            max(
                0.0,
                min(
                    1.0,
                    sum(value for key, value in components.items() if key.endswith("_contribution"))
                    - components["counter_evidence_penalty"]
                    - components["low_diversity_penalty"],
                ),
            ),
            4,
        )
        scored.append((draft, score, components))

    scored.sort(
        key=lambda item: (
            -item[1],
            item[0].category,
            item[0].affected_asset or "",
            item[0].title,
        )
    )

    hypotheses = tuple(
        _to_ranked(draft, score, components, rank=index)
        for index, (draft, score, components) in enumerate(scored, start=1)
    )
    warnings: list[str] = []
    status: DiagnosisStatus = "ranked"
    top_id: str | None = hypotheses[0].hypothesis_id if hypotheses else None

    if not hypotheses or hypotheses[0].score < policy.min_confidence:
        status = "inconclusive"
        top_id = None
        warnings.append(
            "No hypothesis met the minimum confidence threshold; collect more direct evidence."
        )
    elif len(hypotheses) > 1:
        margin = round(hypotheses[0].score - hypotheses[1].score, 4)
        if margin < policy.min_margin:
            status = "inconclusive"
            top_id = None
            warnings.append(
                "The top hypotheses are not sufficiently separated; human review is required."
            )

    return RankingResult(
        status=status,
        hypotheses=hypotheses,
        top_hypothesis_id=top_id,
        warnings=tuple(warnings),
    )


def _score_components(
    draft: HypothesisDraft,
    evidence_by_id: dict[str, EvidenceItem],
    policy: RankingPolicy,
) -> dict[str, float]:
    signals = draft.scoring_signals
    supporting_kinds = {
        evidence_by_id[evidence_id].kind
        for evidence_id in draft.evidence_ids
        if evidence_id in evidence_by_id
    }
    counter_count = sum(
        1 for evidence_id in draft.counter_evidence_ids if evidence_id in evidence_by_id
    )
    return {
        "temporal_contribution": round(
            signals.get("temporal_proximity", 0.0) * policy.temporal_weight, 4
        ),
        "lineage_contribution": round(
            signals.get("lineage_relevance", 0.0) * policy.lineage_weight, 4
        ),
        "metric_contribution": round(
            signals.get("metric_explanation", 0.0) * policy.metric_weight, 4
        ),
        "quality_contribution": round(
            signals.get("quality_corroboration", 0.0) * policy.quality_weight, 4
        ),
        "specificity_contribution": round(
            signals.get("specificity", 0.0) * policy.specificity_weight, 4
        ),
        "counter_evidence_penalty": round(
            min(0.24, counter_count * policy.counter_evidence_penalty), 4
        ),
        "low_diversity_penalty": (
            policy.low_diversity_penalty if len(supporting_kinds) < 2 else 0.0
        ),
    }


def _to_ranked(
    draft: HypothesisDraft,
    score: float,
    components: dict[str, float],
    *,
    rank: int,
) -> RootCauseHypothesis:
    return RootCauseHypothesis(
        hypothesis_id=f"H{rank:03d}",
        rank=rank,
        category=draft.category,
        title=draft.title,
        affected_asset=draft.affected_asset,
        affected_fields=draft.affected_fields,
        confidence=_confidence_label(score),
        score=score,
        score_components=components,
        evidence_ids=draft.evidence_ids,
        counter_evidence_ids=draft.counter_evidence_ids,
        rationale=draft.rationale,
        recommended_next_checks=draft.recommended_next_checks,
    )


def _confidence_label(score: float) -> Literal["high", "medium", "low"]:
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"
