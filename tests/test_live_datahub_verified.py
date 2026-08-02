# Test truthful MCP capability verification without contacting DataHub or MCP.
"""Contract tests for the definitive live DataHub verification wrapper."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)"
DEPLOYMENT_URN = (
    "urn:li:mlModelDeployment:(urn:li:dataPlatform:kserve,churn-api-prod,PROD)"
)


def _load_script() -> Any:
    sys.path.insert(0, str(SCRIPTS))
    try:
        path = SCRIPTS / "run_live_datahub_verified.py"
        spec = importlib.util.spec_from_file_location("run_live_datahub_verified", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_mcp_model_context_is_verified_from_exact_model_and_lineage() -> None:
    module = _load_script()
    result = module._mcp_model_context_evidence(
        model_snapshot={
            "provider": "mcp",
            "source_urn": MODEL_URN,
            "entity": {"urn": MODEL_URN},
            "upstream": [{"urn": "urn:li:dataset:training"}],
            "downstream": [{"urn": "urn:li:mlFeature:spend"}],
        },
        model_urn=MODEL_URN,
    )

    assert result["verified"] is True
    assert result["provider_matches"] is True
    assert result["source_urn_matches"] is True
    assert result["model_urn_observed"] is True


def test_mcp_model_context_rejects_wrong_provider() -> None:
    module = _load_script()
    result = module._mcp_model_context_evidence(
        model_snapshot={
            "provider": "sdk",
            "source_urn": MODEL_URN,
            "entity": {"urn": MODEL_URN},
            "upstream": [{"urn": "urn:li:dataset:training"}],
        },
        model_urn=MODEL_URN,
    )

    assert result["verified"] is False
    assert result["provider_matches"] is False


def test_reclassification_removes_unsupported_mcp_relationship_claim(
    tmp_path: Path,
) -> None:
    module = _load_script()
    module.ARTIFACTS = tmp_path

    _write_json(
        tmp_path / "complete_summary.json",
        {
            "status": "failed",
            "model_urn": MODEL_URN,
            "deployment_urn": DEPLOYMENT_URN,
            "checks": {
                "sdk_provider_verified": True,
                "mcp_provider_verified": True,
                "sdk_ml_lineage_verified": True,
                "mcp_ml_lineage_verified": True,
                "sdk_model_deployment_link_verified": True,
                "mcp_model_deployment_link_verified": False,
                "live_datahub_writeback_verified": True,
                "live_datahub_writeback_idempotent": True,
            },
        },
    )
    _write_json(
        tmp_path / "model_deployment_relationship.json",
        {
            "model_urn": MODEL_URN,
            "deployment_urn": DEPLOYMENT_URN,
        },
    )
    _write_json(
        tmp_path / "mcp_model_context.json",
        {
            "provider": "mcp",
            "source_urn": MODEL_URN,
            "entity": {"urn": MODEL_URN},
            "upstream": [{"urn": "urn:li:dataset:training"}],
            "downstream": [{"urn": "urn:li:mlFeature:spend"}],
        },
    )

    corrected, summary = module._reclassify_supported_capabilities()

    assert corrected is True
    assert summary["status"] == "complete"
    assert "mcp_model_deployment_link_verified" not in summary["checks"]
    assert summary["checks"]["mcp_model_context_verified"] is True
    assert summary["checks"]["datahub_model_deployment_link_verified"] is True
    assert summary["model_deployment_relationship"]["verified_by"] == (
        "DataHub SDK model metadata"
    )

    relationship = json.loads(
        (tmp_path / "model_deployment_relationship.json").read_text(
            encoding="utf-8"
        )
    )
    assert relationship["mcp_relationship_observation"]["exposed"] is False
    assert relationship["mcp_relationship_observation"]["required_for_pass"] is False


def test_reclassification_does_not_hide_other_failures(tmp_path: Path) -> None:
    module = _load_script()
    module.ARTIFACTS = tmp_path

    _write_json(
        tmp_path / "complete_summary.json",
        {
            "status": "failed",
            "model_urn": MODEL_URN,
            "checks": {
                "sdk_model_deployment_link_verified": True,
                "mcp_model_deployment_link_verified": False,
                "live_datahub_writeback_verified": False,
            },
        },
    )
    _write_json(tmp_path / "model_deployment_relationship.json", {})
    _write_json(
        tmp_path / "mcp_model_context.json",
        {
            "provider": "mcp",
            "source_urn": MODEL_URN,
            "entity": {"urn": MODEL_URN},
            "upstream": [{"urn": "urn:li:dataset:training"}],
        },
    )

    corrected, _ = module._reclassify_supported_capabilities()

    assert corrected is False
