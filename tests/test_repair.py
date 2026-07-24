"""Tests for constrained repair generation, guardrails and validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from modelguard.repair import (
    ConstrainedRepairGenerator,
    PatchGuardPolicy,
    RepairCase,
    RepairGenerationError,
    RepairValidationError,
    RepairValidator,
    evaluate_patch_guard,
)
from modelguard.reporting import render_repair_markdown

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _diagnosis() -> dict[str, object]:
    return {
        "diagnosis_id": "diag-phase4-test",
        "status": "ranked",
        "top_hypothesis_id": "H001",
        "hypotheses": [
            {
                "hypothesis_id": "H001",
                "category": "feature_transformation",
                "confidence": "high",
                "score": 1.0,
                "affected_fields": [
                    "account_age_months",
                    "monthly_spend",
                    "total_spend",
                ],
            }
        ],
        "evidence": [
            {
                "kind": "change",
                "attributes": {"path": "src/features/customer_features.py"},
            }
        ],
    }


def _case() -> RepairCase:
    return RepairCase.from_dict(_read_json(ROOT / "examples" / "repair_case.json"))


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "demo" / "broken_change", workspace)
    return workspace


def test_generate_and_validate_repair(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    case = _case()
    plan = ConstrainedRepairGenerator().generate(
        diagnosis=_diagnosis(),
        case=case,
        workspace=workspace,
    )
    assert plan.category == "feature_transformation"
    assert "if account_age_months <= 0:" in plan.patches[0].patched_content
    assert evaluate_patch_guard(plan, case).approved

    original = (workspace / case.target_file).read_text(encoding="utf-8")
    report = RepairValidator().validate(
        plan=plan,
        case=case,
        evaluation=_read_json(ROOT / "examples" / "evaluation_failed.json"),
        workspace=workspace,
    )
    assert report.status == "validated"
    assert report.metric_restored
    assert report.source_workspace_unchanged
    assert (workspace / case.target_file).read_text(encoding="utf-8") == original
    assert report.post_repair_evaluation is not None
    assert report.post_repair_evaluation["gate"]["candidate"] == 0.842
    assert all(command.passed for command in report.commands)
    markdown = render_repair_markdown(plan, report)
    assert "validated" in markdown
    assert "Source workspace unchanged" in markdown


def test_generation_rejects_low_confidence(tmp_path: Path) -> None:
    diagnosis = _diagnosis()
    diagnosis["hypotheses"][0]["confidence"] = "medium"
    with pytest.raises(RepairGenerationError, match="high confidence"):
        ConstrainedRepairGenerator().generate(
            diagnosis=diagnosis,
            case=_case(),
            workspace=_workspace(tmp_path),
        )


def test_guard_rejects_protected_path(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    diagnosis = _diagnosis()
    diagnosis["evidence"][0]["attributes"]["path"] = ".github/workflows/modelguard.yml"
    case_value = _read_json(ROOT / "examples" / "repair_case.json")
    case_value["target_file"] = ".github/workflows/modelguard.yml"
    case_value["allowed_paths"] = [".github/"]
    target = workspace / ".github" / "workflows" / "modelguard.yml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "def calculate_monthly_spend(total_spend, account_age_months):\n"
        "    return total_spend / account_age_months\n",
        encoding="utf-8",
    )
    case = RepairCase.from_dict(case_value)
    plan = ConstrainedRepairGenerator().generate(
        diagnosis=diagnosis,
        case=case,
        workspace=workspace,
    )
    decision = evaluate_patch_guard(plan, case, PatchGuardPolicy())
    assert not decision.approved
    assert any("protected" in violation for violation in decision.violations)


def test_validation_fails_when_metric_is_not_restored(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    case_value = _read_json(ROOT / "examples" / "repair_case.json")
    script = (
        "import json, pathlib; "
        "p=pathlib.Path('artifacts/post_repair_evaluation.json'); "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text(json.dumps({'metric':'f1_score','candidate':0.78}))"
    )
    case_value["validation"]["commands"] = [["{python}", "-c", script]]
    case = RepairCase.from_dict(case_value)
    plan = ConstrainedRepairGenerator().generate(
        diagnosis=_diagnosis(),
        case=case,
        workspace=workspace,
    )
    report = RepairValidator().validate(
        plan=plan,
        case=case,
        evaluation=_read_json(ROOT / "examples" / "evaluation_failed.json"),
        workspace=workspace,
    )
    assert report.status == "failed"
    assert not report.metric_restored


def test_validation_rejects_unapproved_executable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    case_value = _read_json(ROOT / "examples" / "repair_case.json")
    case_value["validation"]["commands"] = [["bash", "-lc", "true"]]
    case = RepairCase.from_dict(case_value)
    plan = ConstrainedRepairGenerator().generate(
        diagnosis=_diagnosis(),
        case=case,
        workspace=workspace,
    )
    with pytest.raises(RepairValidationError, match="not allowed"):
        RepairValidator().validate(
            plan=plan,
            case=case,
            evaluation=_read_json(ROOT / "examples" / "evaluation_failed.json"),
            workspace=workspace,
        )
