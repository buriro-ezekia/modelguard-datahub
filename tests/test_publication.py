"""Tests for Phase 5 publication and write-back."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from modelguard.reporting import (
    DataHubIncidentWriter,
    GitHubCommentWriter,
    PublicationCoordinator,
    PublicationError,
    PublicationInputs,
    build_publication_plan,
    render_publication_markdown,
)


def _inputs() -> PublicationInputs:
    diagnosis = {
        "diagnosis_id": "diag-test",
        "status": "ranked",
        "repository": "buriro-ezekia/modelguard-datahub",
        "pull_request": 12,
        "source_urn": "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn,PROD)",
        "metric": "f1_score",
        "top_hypothesis_id": "H001",
        "hypotheses": [
            {
                "hypothesis_id": "H001",
                "rank": 1,
                "category": "feature_transformation",
                "title": "Changed feature transformation introduced invalid values",
                "affected_asset": (
                    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
                    "analytics.customer_features,PROD)"
                ),
                "affected_fields": [
                    "account_age_months",
                    "monthly_spend",
                    "total_spend",
                ],
                "confidence": "high",
                "score": 1.0,
            }
        ],
    }
    repair_plan = {
        "repair_id": "repair-test",
        "diagnosis_id": "diag-test",
        "strategy": "guarded_division",
        "status": "proposed",
    }
    validation = {
        "validation_id": "validation-test",
        "repair_id": "repair-test",
        "status": "validated",
        "patch_guard": {"approved": True},
        "metric_restored": True,
        "source_workspace_unchanged": True,
        "commands": [
            {"command": ["{python}", "-m", "py_compile"], "return_code": 0},
            {"command": ["{python}", "-m", "pytest"], "return_code": 0},
        ],
        "pre_repair_evaluation": {
            "metric": "f1_score",
            "baseline": 0.842,
            "candidate": 0.771,
        },
        "post_repair_evaluation": {
            "metric": "f1_score",
            "candidate": 0.842,
            "invalid_values": 0,
        },
    }
    patch = (
        "--- a/src/features/customer_features.py\n"
        "+++ b/src/features/customer_features.py\n"
        "+    if account_age_months <= 0:\n"
        "+        return 0.0\n"
    )
    return PublicationInputs(
        diagnosis=diagnosis,
        repair_plan=repair_plan,
        validation=validation,
        patch=patch,
        repository="buriro-ezekia/modelguard-datahub",
        pull_request=12,
    )


def test_fixture_publication_is_idempotent(tmp_path: Path) -> None:
    github_state = tmp_path / "github.json"
    datahub_state = tmp_path / "datahub.json"
    coordinator = PublicationCoordinator(
        github_writer=GitHubCommentWriter(
            mode="fixture",
            fixture_state=github_state,
        ),
        datahub_writer=DataHubIncidentWriter(
            mode="fixture",
            fixture_state=datahub_state,
        ),
    )

    first = coordinator.publish(_inputs(), apply=True)
    second = coordinator.publish(_inputs(), apply=True)

    assert first.status == "published"
    assert [item.action for item in first.channels] == [
        "created",
        "raised_and_resolved",
    ]
    assert second.status == "published"
    assert [item.action for item in second.channels] == ["noop", "noop"]
    assert first.delivery_id == second.delivery_id

    comments = json.loads(github_state.read_text(encoding="utf-8"))["comments"]
    incidents = json.loads(datahub_state.read_text(encoding="utf-8"))["incidents"]
    assert len(comments) == 1
    assert len(incidents) == 1
    assert incidents[0]["state"] == "RESOLVED"


def test_dry_run_creates_no_fixture_state(tmp_path: Path) -> None:
    github_state = tmp_path / "github.json"
    datahub_state = tmp_path / "datahub.json"
    coordinator = PublicationCoordinator(
        github_writer=GitHubCommentWriter(
            mode="fixture",
            fixture_state=github_state,
        ),
        datahub_writer=DataHubIncidentWriter(
            mode="fixture",
            fixture_state=datahub_state,
        ),
    )

    receipt = coordinator.publish(_inputs(), apply=False)

    assert receipt.status == "dry_run"
    assert [item.status for item in receipt.channels] == ["planned", "planned"]
    assert not github_state.exists()
    assert not datahub_state.exists()


def test_publication_refuses_unvalidated_repair() -> None:
    inputs = _inputs()
    inputs.validation["status"] = "failed"

    with pytest.raises(PublicationError, match="validated repair"):
        inputs.validate()


def test_plan_and_markdown_are_stable() -> None:
    inputs = _inputs()
    first = build_publication_plan(inputs)
    second = build_publication_plan(inputs)

    assert first.delivery_id == second.delivery_id
    assert first.marker in first.github_comment
    assert "0.771" in first.github_comment
    assert "0.842" in first.github_comment

    coordinator = PublicationCoordinator(
        github_writer=GitHubCommentWriter(mode="off"),
        datahub_writer=DataHubIncidentWriter(mode="off"),
    )
    receipt = coordinator.publish(inputs, apply=False)
    rendered = render_publication_markdown(receipt)
    assert "Publication Report" in rendered
    assert "External writes are disabled" in rendered


def test_live_github_writer_creates_comment_without_leaking_token() -> None:
    calls: list[tuple[str, str, dict[str, str], dict[str, Any] | None]] = []

    def transport(
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
    ) -> Any:
        calls.append((method, url, headers, payload))
        if method == "GET":
            return []
        return {"id": 44, "html_url": "https://github.com/example/comment/44"}

    plan = build_publication_plan(_inputs())
    receipt = GitHubCommentWriter(
        mode="live",
        token="super-secret",
        transport=transport,
    ).publish(plan, apply=True)

    assert receipt.status == "published"
    assert receipt.action == "created"
    assert [call[0] for call in calls] == ["GET", "POST"]
    assert calls[1][2]["Authorization"] == "Bearer super-secret"
    assert "super-secret" not in json.dumps(receipt.to_dict())


def test_live_datahub_writer_raises_and_resolves_incident() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def transport(
        query: str,
        variables: dict[str, Any],
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        calls.append((query, variables))
        if "ModelGuardIncidents" in query:
            return {"data": {"dataset": {"incidents": {"incidents": []}}}}
        if "RaiseModelGuardIncident" in query:
            return {"data": {"raiseIncident": "urn:li:incident:fixture-live"}}
        return {"data": {"updateIncidentStatus": True}}

    plan = build_publication_plan(_inputs())
    receipt = DataHubIncidentWriter(
        mode="live",
        graphql_url="https://datahub.example/api/graphql",
        token="datahub-secret",
        transport=transport,
    ).publish(plan, apply=True)

    assert receipt.status == "published"
    assert receipt.action == "raised_and_resolved"
    assert receipt.external_id == "urn:li:incident:fixture-live"
    assert len(calls) == 4
    assert calls[-1][1]["input"]["state"] == "RESOLVED"
    assert "datahub-secret" not in json.dumps(receipt.to_dict())


def test_live_datahub_writer_waits_until_resolved_incident_is_queryable() -> None:
    plan = build_publication_plan(_inputs())
    marker = f"[modelguard-delivery:{plan.delivery_id}]"
    state = {"resolved": False, "resolved_queries": 0}

    def transport(
        query: str,
        variables: dict[str, Any],
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        if "ModelGuardIncidents" in query:
            incidents: list[dict[str, Any]] = []
            if state["resolved"] and variables.get("state") == "RESOLVED":
                state["resolved_queries"] += 1
                if state["resolved_queries"] >= 2:
                    incidents = [
                        {
                            "urn": "urn:li:incident:eventually-visible",
                            "description": marker,
                            "status": {"state": "RESOLVED"},
                        }
                    ]
            return {"data": {"dataset": {"incidents": {"incidents": incidents}}}}
        if "RaiseModelGuardIncident" in query:
            return {"data": {"raiseIncident": "urn:li:incident:eventually-visible"}}
        state["resolved"] = True
        return {"data": {"updateIncidentStatus": True}}

    receipt = DataHubIncidentWriter(
        mode="live",
        graphql_url="https://datahub.example/api/graphql",
        token="token",
        transport=transport,
        confirm_visibility=True,
        consistency_attempts=3,
        consistency_delay_seconds=0,
        sleeper=lambda _seconds: None,
    ).publish(plan, apply=True)

    assert receipt.status == "published"
    assert receipt.action == "raised_and_resolved"
    assert receipt.details["visibility_confirmed"] is True
    assert state["resolved_queries"] == 2


def test_live_datahub_writer_noops_for_resolved_delivery() -> None:
    plan = build_publication_plan(_inputs())
    marker = f"[modelguard-delivery:{plan.delivery_id}]"

    def transport(
        query: str,
        variables: dict[str, Any],
        url: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        if variables.get("state") == "ACTIVE":
            incidents: list[dict[str, Any]] = []
        else:
            incidents = [
                {
                    "urn": "urn:li:incident:existing",
                    "description": marker,
                    "status": {"state": "RESOLVED"},
                }
            ]
        return {"data": {"dataset": {"incidents": {"incidents": incidents}}}}

    receipt = DataHubIncidentWriter(
        mode="live",
        graphql_url="https://datahub.example/api/graphql",
        token="token",
        transport=transport,
    ).publish(plan, apply=True)

    assert receipt.status == "noop"
    assert receipt.action == "noop"
