"""Phase 3 diagnosis orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from modelguard.diagnosis.hypotheses import (
    CandidateGenerator,
    ChangeSet,
    DiagnosisReport,
    EvidenceBuilder,
    diagnosis_id,
)
from modelguard.diagnosis.ranking import RankingPolicy, rank_hypotheses
from modelguard.models import ContextSnapshot


class DiagnosisError(RuntimeError):
    """Raised when supplied diagnosis inputs are invalid or inconsistent."""


@dataclass(slots=True)
class DiagnosisAgent:
    """Generate and rank evidence-backed hypotheses without inventing facts."""

    policy: RankingPolicy = field(default_factory=RankingPolicy)

    def diagnose(
        self,
        *,
        evaluation: dict[str, Any],
        context: ContextSnapshot,
        changes: ChangeSet,
        generated_at: str | None = None,
    ) -> DiagnosisReport:
        self._validate_inputs(evaluation, context, changes)
        evidence = EvidenceBuilder().build(evaluation, context, changes)
        drafts = CandidateGenerator().generate(evidence, context)
        ranking = rank_hypotheses(drafts, evidence, self.policy)

        warnings = list(ranking.warnings)
        if not changes.changed_files:
            warnings.append("No changed-file evidence was supplied.")
        if not changes.observations:
            warnings.append(
                "No deterministic runtime or data-profile observations were supplied."
            )
        if context.provider == "fixture":
            warnings.append(
                "Diagnosis used deterministic fixture context, not a live DataHub instance."
            )

        return DiagnosisReport(
            diagnosis_id=diagnosis_id(evaluation, context, changes),
            generated_at=generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
            status=ranking.status,
            source_urn=context.source_urn,
            repository=changes.repository,
            commit_sha=changes.commit_sha,
            pull_request=changes.pull_request,
            metric=str(evaluation["metric"]),
            top_hypothesis_id=ranking.top_hypothesis_id,
            hypotheses=ranking.hypotheses,
            evidence=evidence,
            policy=self.policy.to_dict(),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _validate_inputs(
        evaluation: dict[str, Any],
        context: ContextSnapshot,
        changes: ChangeSet,
    ) -> None:
        if not evaluation.get("metric"):
            raise DiagnosisError("evaluation must contain a metric")
        if evaluation.get("status") != "failed":
            raise DiagnosisError("diagnosis requires a failed Phase 1 evaluation")
        if not context.source_urn:
            raise DiagnosisError("context snapshot must contain source_urn")
        if not changes.repository:
            raise DiagnosisError("change set must contain repository")
        if not changes.commit_sha:
            raise DiagnosisError("change set must contain commit_sha")
