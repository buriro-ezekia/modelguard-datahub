"""Human-readable reporting for constrained repair validation."""

from __future__ import annotations

from modelguard.repair.generator import RepairPlan
from modelguard.repair.validator import RepairValidationReport


def render_repair_markdown(
    plan: RepairPlan,
    validation: RepairValidationReport,
) -> str:
    """Render a review-ready repair and validation report."""
    lines = [
        "# ModelGuard Validated Repair Report",
        "",
        f"- **Repair:** `{plan.repair_id}`",
        f"- **Diagnosis:** `{plan.diagnosis_id}`",
        f"- **Hypothesis:** `{plan.hypothesis_id}`",
        f"- **Status:** `{validation.status}`",
        f"- **Strategy:** `{plan.strategy}`",
        f"- **Source workspace unchanged:** `{validation.source_workspace_unchanged}`",
        "",
        "## Proposed change",
        "",
        plan.rationale,
        "",
        "```diff",
        plan.combined_diff.rstrip(),
        "```",
        "",
        "## Patch guard",
        "",
        f"Approved: **{validation.patch_guard.approved}**",
        "",
    ]
    for check in validation.patch_guard.checks:
        lines.append(f"- PASS — {check}")
    for violation in validation.patch_guard.violations:
        lines.append(f"- FAIL — {violation}")
    lines.extend(["", "## Independent validation", ""])
    for result in validation.commands:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"- {status} — `{' '.join(result.command)}` "
            f"(exit {result.return_code}, {result.duration_seconds:.4f}s)"
        )
    lines.extend(["", "## Metric gate", ""])
    if validation.post_repair_evaluation is None:
        lines.append("No valid post-repair metric was produced.")
    else:
        gate = validation.post_repair_evaluation.get("gate", {})
        lines.extend(
            [
                f"- Baseline: `{gate.get('baseline')}`",
                f"- Repaired candidate: `{gate.get('candidate')}`",
                f"- Maximum regression: `{gate.get('maximum_allowed_regression')}`",
                f"- Gate status: **{gate.get('status')}**",
            ]
        )
    if validation.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation.warnings)
    lines.extend(
        [
            "",
            "## Safety statement",
            "",
            "Validation occurred in a temporary workspace. This report does not merge or apply "
            "the patch to the source branch; a human-reviewed pull request remains required.",
            "",
        ]
    )
    return "\n".join(lines)
