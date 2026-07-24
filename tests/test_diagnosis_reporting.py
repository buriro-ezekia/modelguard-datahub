"""Tests for Phase 3 Markdown reporting."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.diagnosis import ChangeSet, DiagnosisAgent
from modelguard.models import ContextSnapshot
from modelguard.reporting import render_diagnosis_markdown


def test_markdown_report_contains_decision_and_evidence_registry() -> None:
    evaluation = json.loads(
        Path("examples/evaluation_failed.json").read_text(encoding="utf-8")
    )
    context = ContextSnapshot.from_dict(
        json.loads(Path("examples/context_snapshot.json").read_text(encoding="utf-8"))
    )
    changes = ChangeSet.from_dict(
        json.loads(Path("examples/regression_case.json").read_text(encoding="utf-8"))
    )
    report = DiagnosisAgent().diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
        generated_at="2026-07-24T00:00:00+00:00",
    )

    rendered = render_diagnosis_markdown(report)

    assert "# ModelGuard Root-Cause Report" in rendered
    assert "Changed feature transformation introduced invalid values" in rendered
    assert "## Evidence registry" in rendered
    assert "E001" in rendered
    assert "does not prove causality" in rendered
