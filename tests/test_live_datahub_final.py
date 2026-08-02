# Test final live verification without contacting DataHub, Docker or the MCP server.
"""Contract tests for model-side deployment relationship verification."""

from __future__ import annotations

import importlib.util
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
        path = SCRIPTS / "run_live_datahub_final.py"
        spec = importlib.util.spec_from_file_location("run_live_datahub_final", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_relationship_is_verified_from_model_entity_metadata() -> None:
    module = _load_script()

    result = module._model_deployment_evidence(
        model_snapshot={
            "source_urn": MODEL_URN,
            "entity": {
                "urn": MODEL_URN,
                "raw": {"deployments": [DEPLOYMENT_URN]},
            },
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["model_entity_metadata"]


def test_relationship_is_verified_from_model_downstream() -> None:
    module = _load_script()

    result = module._model_deployment_evidence(
        model_snapshot={
            "source_urn": MODEL_URN,
            "downstream": [{"urn": DEPLOYMENT_URN}],
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["model_downstream"]


def test_relationship_is_verified_from_provider_metadata() -> None:
    module = _load_script()

    result = module._model_deployment_evidence(
        model_snapshot={
            "source_urn": MODEL_URN,
            "provider_metadata": {
                "entity_urns": [MODEL_URN, DEPLOYMENT_URN],
            },
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["provider_metadata"]


def test_relationship_does_not_pass_from_model_source_urn_alone() -> None:
    module = _load_script()

    result = module._model_deployment_evidence(
        model_snapshot={"source_urn": MODEL_URN},
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is False
    assert result["verification_sources"] == []
