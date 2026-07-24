"""Tests for Phase 3 evidence generation and root-cause ranking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modelguard.diagnosis import ChangeSet, DiagnosisAgent, DiagnosisError
from modelguard.diagnosis.ranking import RankingPolicy
from modelguard.models import ContextSnapshot, EntityContext

EXAMPLES = Path("examples")


def _load(path: str) -> dict[str, object]:
    return json.loads((EXAMPLES / path).read_text(encoding="utf-8"))


def _demo_inputs() -> tuple[dict[str, object], ContextSnapshot, ChangeSet]:
    return (
        _load("evaluation_failed.json"),
        ContextSnapshot.from_dict(_load("context_snapshot.json")),
        ChangeSet.from_dict(_load("regression_case.json")),
    )


def test_diagnosis_ranks_changed_transformation_first() -> None:
    evaluation, context, changes = _demo_inputs()

    report = DiagnosisAgent().diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
        generated_at="2026-07-24T00:00:00+00:00",
    )

    assert report.status == "ranked"
    assert report.top_hypothesis_id == "H001"
    assert report.hypotheses[0].category == "feature_transformation"
    assert report.hypotheses[0].confidence == "high"
    assert report.hypotheses[0].score == 1.0
    assert report.hypotheses[0].affected_asset is not None
    assert "monthly_spend" in report.hypotheses[0].affected_fields
    assert report.hypotheses[1].category == "source_data_quality"
    assert report.hypotheses[1].score < report.hypotheses[0].score


def test_every_hypothesis_reference_resolves_to_evidence() -> None:
    evaluation, context, changes = _demo_inputs()
    report = DiagnosisAgent().diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
    )
    evidence_ids = {item.evidence_id for item in report.evidence}

    for hypothesis in report.hypotheses:
        assert set(hypothesis.evidence_ids) <= evidence_ids
        assert set(hypothesis.counter_evidence_ids) <= evidence_ids


def test_agent_abstains_when_only_metric_failure_is_available() -> None:
    evaluation = _load("evaluation_failed.json")
    context = ContextSnapshot(
        source_urn="urn:li:mlModel:test",
        provider="fixture",
        generated_at="2026-07-24T00:00:00+00:00",
        entity=EntityContext(urn="urn:li:mlModel:test"),
    )
    changes = ChangeSet(repository="example/repository", commit_sha="abc123")

    report = DiagnosisAgent().diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
    )

    assert report.status == "inconclusive"
    assert report.top_hypothesis_id is None
    assert report.hypotheses[0].category == "unknown"
    assert any("minimum confidence" in warning for warning in report.warnings)


def test_agent_abstains_when_top_candidates_are_not_separated() -> None:
    evaluation, context, changes = _demo_inputs()
    agent = DiagnosisAgent(policy=RankingPolicy(min_margin=0.5))

    report = agent.diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
    )

    assert report.status == "inconclusive"
    assert report.top_hypothesis_id is None
    assert any("not sufficiently separated" in warning for warning in report.warnings)


def test_diagnosis_rejects_non_failed_evaluation() -> None:
    _, context, changes = _demo_inputs()

    with pytest.raises(DiagnosisError, match="failed Phase 1"):
        DiagnosisAgent().diagnose(
            evaluation={"metric": "f1_score", "status": "passed"},
            context=context,
            changes=changes,
        )
