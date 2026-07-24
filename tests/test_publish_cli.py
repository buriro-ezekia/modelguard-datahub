"""CLI tests for Phase 5 publication."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.cli import main


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_publish_cli_is_idempotent_in_fixture_mode(tmp_path: Path) -> None:
    diagnosis = tmp_path / "diagnosis.json"
    plan = tmp_path / "plan.json"
    validation = tmp_path / "validation.json"
    patch = tmp_path / "patch.diff"
    receipt = tmp_path / "receipt.json"
    repeat = tmp_path / "repeat.json"
    markdown = tmp_path / "publication.md"
    comment = tmp_path / "comment.md"
    github_state = tmp_path / "github-state.json"
    datahub_state = tmp_path / "datahub-state.json"

    _write(
        diagnosis,
        {
            "diagnosis_id": "diag-cli",
            "status": "ranked",
            "repository": "buriro-ezekia/modelguard-datahub",
            "pull_request": 12,
            "source_urn": "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn,PROD)",
            "hypotheses": [
                {
                    "title": "Changed feature transformation introduced invalid values",
                    "affected_asset": (
                        "urn:li:dataset:(urn:li:dataPlatform:dbt,"
                        "analytics.customer_features,PROD)"
                    ),
                    "affected_fields": ["monthly_spend", "account_age_months"],
                    "confidence": "high",
                    "score": 1.0,
                }
            ],
        },
    )
    _write(
        plan,
        {
            "repair_id": "repair-cli",
            "diagnosis_id": "diag-cli",
            "strategy": "guarded_division",
        },
    )
    _write(
        validation,
        {
            "validation_id": "validation-cli",
            "repair_id": "repair-cli",
            "status": "validated",
            "patch_guard": {"approved": True},
            "metric_restored": True,
            "source_workspace_unchanged": True,
            "commands": [{"return_code": 0}],
            "pre_repair_evaluation": {
                "metric": "f1_score",
                "candidate": 0.771,
            },
            "post_repair_evaluation": {
                "metric": "f1_score",
                "candidate": 0.842,
                "invalid_values": 0,
            },
        },
    )
    patch.write_text(
        "--- a/src/features.py\n+++ b/src/features.py\n+if denominator <= 0:\n",
        encoding="utf-8",
    )

    common = [
        "publish",
        "--diagnosis",
        str(diagnosis),
        "--repair-plan",
        str(plan),
        "--validation",
        str(validation),
        "--patch",
        str(patch),
        "--github-mode",
        "fixture",
        "--datahub-mode",
        "fixture",
        "--github-state",
        str(github_state),
        "--datahub-state",
        str(datahub_state),
        "--apply",
    ]

    first_code = main(
        [
            *common,
            "--output",
            str(receipt),
            "--markdown-output",
            str(markdown),
            "--comment-output",
            str(comment),
        ]
    )
    second_code = main([*common, "--output", str(repeat)])

    first = json.loads(receipt.read_text(encoding="utf-8"))
    second = json.loads(repeat.read_text(encoding="utf-8"))
    github = json.loads(github_state.read_text(encoding="utf-8"))
    datahub = json.loads(datahub_state.read_text(encoding="utf-8"))

    assert first_code == 0
    assert second_code == 0
    assert first["status"] == "published"
    assert [item["action"] for item in first["channels"]] == [
        "created",
        "raised_and_resolved",
    ]
    assert [item["action"] for item in second["channels"]] == ["noop", "noop"]
    assert len(github["comments"]) == 1
    assert len(datahub["incidents"]) == 1
    assert datahub["incidents"][0]["state"] == "RESOLVED"
    assert "modelguard:delivery" in comment.read_text(encoding="utf-8")
    assert "Publication Report" in markdown.read_text(encoding="utf-8")
