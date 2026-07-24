"""Markdown rendering for evidence-backed diagnosis reports."""

from __future__ import annotations

from modelguard.diagnosis.hypotheses import DiagnosisReport


def render_diagnosis_markdown(report: DiagnosisReport) -> str:
    """Render a review-ready diagnosis while preserving evidence references."""
    evidence = {item.evidence_id: item for item in report.evidence}
    lines = [
        "# ModelGuard Root-Cause Report",
        "",
        f"- **Diagnosis:** `{report.diagnosis_id}`",
        f"- **Status:** `{report.status}`",
        f"- **Repository:** `{report.repository}`",
        f"- **Commit:** `{report.commit_sha}`",
        f"- **Model:** `{report.source_urn}`",
        f"- **Failed metric:** `{report.metric}`",
        "",
    ]

    if report.top_hypothesis_id is None:
        lines.extend(
            [
                "## Decision",
                "",
                "ModelGuard abstained because the evidence did not meet the configured "
                "confidence and separation thresholds.",
                "",
            ]
        )
    else:
        top = next(
            hypothesis
            for hypothesis in report.hypotheses
            if hypothesis.hypothesis_id == report.top_hypothesis_id
        )
        lines.extend(
            [
                "## Leading diagnosis",
                "",
                f"**{top.title}**",
                "",
                f"Confidence: **{top.confidence}** (`{top.score:.4f}`)",
                "",
                top.rationale,
                "",
                f"Affected asset: `{top.affected_asset or 'not resolved'}`",
                "",
                "Affected fields: "
                + (", ".join(f"`{field}`" for field in top.affected_fields) or "not resolved"),
                "",
            ]
        )

    lines.extend(["## Ranked hypotheses", ""])
    for hypothesis in report.hypotheses:
        lines.extend(
            [
                f"### {hypothesis.rank}. {hypothesis.title}",
                "",
                f"- Category: `{hypothesis.category}`",
                f"- Score: `{hypothesis.score:.4f}` ({hypothesis.confidence})",
                f"- Asset: `{hypothesis.affected_asset or 'not resolved'}`",
                "- Supporting evidence: "
                + (", ".join(f"`{item}`" for item in hypothesis.evidence_ids) or "none"),
                "- Counter-evidence: "
                + (", ".join(f"`{item}`" for item in hypothesis.counter_evidence_ids) or "none"),
                "",
                hypothesis.rationale,
                "",
                "Recommended checks:",
            ]
        )
        lines.extend(f"- {check}" for check in hypothesis.recommended_next_checks)
        lines.append("")

    lines.extend(["## Evidence registry", ""])
    for evidence_id in sorted(evidence):
        item = evidence[evidence_id]
        lines.extend(
            [
                f"### {evidence_id} — {item.kind}",
                "",
                item.summary,
                "",
                f"Source: `{item.source}` · Strength: `{item.strength:.3f}`",
                "",
            ]
        )

    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")

    lines.extend(
        [
            "## Safety statement",
            "",
            "This report ranks hypotheses; it does not prove causality or authorise a code change. "
            "A repair must be independently generated, constrained and validated in Phase 4.",
            "",
        ]
    )
    return "\n".join(lines)
