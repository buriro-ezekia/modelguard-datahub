# Test final live verification without contacting DataHub, Docker or the MCP server.
"""Contract tests for symmetric model-deployment lineage verification."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load_script() -> Any:
    sys.path.insert(0, str(SCRIPTS))
    try:
        path = SCRIPTS / "run_live_datahub_final.py"
        spec = importlib.util.spec_from_file_location("run_live_datahub_final", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_relationship_is_verified_from_model_downstream() -> None:
    module = _load_script()
    model_urn = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)"
    deployment_urn = "urn:li:mlModelDeployment:(urn:li:dataPlatform:mlflow,churn-api-prod,PROD)"

    result = module._relationship_evidence(
        model_snapshot={"downstream": [{"urn": deployment_urn}]},
        deployment_snapshot={"source_urn": deployment_urn},
        model_urn=model_urn,
        deployment_urn=deployment_urn,
    )

    assert result["verified"] is True
    assert result["verification_direction"] == "model_downstream"


def test_relationship_is_verified_from_deployment_upstream() -> None:
    module = _load_script()
    model_urn = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)"
    deployment_urn = "urn:li:mlModelDeployment:(urn:li:dataPlatform:mlflow,churn-api-prod,PROD)"

    result = module._relationship_evidence(
        model_snapshot={"source_urn": model_urn},
        deployment_snapshot={
            "source_urn": deployment_urn,
            "upstream": [{"urn": model_urn}],
        },
        model_urn=model_urn,
        deployment_urn=deployment_urn,
    )

    assert result["verified"] is True
    assert result["verification_direction"] == "deployment_upstream"


def test_relationship_does_not_pass_from_source_urns_alone() -> None:
    module = _load_script()
    model_urn = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)"
    deployment_urn = "urn:li:mlModelDeployment:(urn:li:dataPlatform:mlflow,churn-api-prod,PROD)"

    result = module._relationship_evidence(
        model_snapshot={"source_urn": model_urn},
        deployment_snapshot={"source_urn": deployment_urn},
        model_urn=model_urn,
        deployment_urn=deployment_urn,
    )

    assert result["verified"] is False
    assert result["verification_direction"] == "not_observed"
