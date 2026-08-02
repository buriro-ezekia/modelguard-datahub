# Test canonical deployment matching without contacting DataHub or MCP.
"""Contract tests for the definitive live DataHub verification wrapper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
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


def test_exact_deployment_urn_is_verified() -> None:
    module = _load_script()
    result = module._model_deployment_evidence(
        model_snapshot={"downstream": [{"urn": DEPLOYMENT_URN}]},
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["model_downstream"]


def test_typed_mcp_identity_is_verified_when_exact_urn_is_absent() -> None:
    module = _load_script()
    result = module._model_deployment_evidence(
        model_snapshot={
            "downstream": [
                {
                    "entity_type": "ML_MODEL_DEPLOYMENT",
                    "name": "churn-api-prod",
                    "platform": "kserve",
                }
            ]
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["model_downstream"]
    assert result["matched_candidates"][0]["name"] == "churnapiprod"


def test_canonicalised_urn_with_trailing_punctuation_is_verified() -> None:
    module = _load_script()
    result = module._model_deployment_evidence(
        model_snapshot={
            "provider_metadata": {"downstream_urns": [DEPLOYMENT_URN + ","]}
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is True
    assert result["verification_sources"] == ["provider_metadata"]


def test_unrelated_downstream_entity_does_not_pass() -> None:
    module = _load_script()
    result = module._model_deployment_evidence(
        model_snapshot={
            "downstream": [
                {
                    "entity_type": "ML_MODEL_DEPLOYMENT",
                    "name": "another-api",
                    "platform": "kserve",
                }
            ]
        },
        deployment_urn=DEPLOYMENT_URN,
    )

    assert result["verified"] is False
    assert result["verification_sources"] == []
