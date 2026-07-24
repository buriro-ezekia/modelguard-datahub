"""Command-line tests for Phase 4 validated repair output."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from modelguard.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_repair_cli_writes_validated_outputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "demo" / "broken_change", workspace)
    diagnosis = tmp_path / "diagnosis.json"
    diagnosis.write_text(
        json.dumps(
            {
                "diagnosis_id": "diag-phase4-cli",
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
                        "attributes": {
                            "path": "src/features/customer_features.py"
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = tmp_path / "repair_plan.json"
    validation = tmp_path / "repair_validation.json"
    patch = tmp_path / "validated_patch.diff"
    markdown = tmp_path / "repair_report.md"
    exit_code = main(
        [
            "repair",
            "--diagnosis",
            str(diagnosis),
            "--evaluation",
            str(ROOT / "examples" / "evaluation_failed.json"),
            "--case",
            str(ROOT / "examples" / "repair_case.json"),
            "--workspace",
            str(workspace),
            "--plan-output",
            str(plan),
            "--validation-output",
            str(validation),
            "--patch-output",
            str(patch),
            "--markdown-output",
            str(markdown),
        ]
    )
    assert exit_code == 0
    assert json.loads(validation.read_text(encoding="utf-8"))["status"] == "validated"
    assert "account_age_months <= 0" in patch.read_text(encoding="utf-8")
    assert "validated" in markdown.read_text(encoding="utf-8")
