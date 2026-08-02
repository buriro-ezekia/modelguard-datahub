"""Contract tests for the optional live DataHub evidence loader."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> Any:
    path = ROOT / "scripts/load_live_ml_lineage.py"
    spec = importlib.util.spec_from_file_location("load_live_ml_lineage", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_ml_loader_builds_serialisable_datahub_aspects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    datahub = pytest.importorskip("datahub")
    del datahub

    from datahub.emitter import rest_emitter

    emitted: list[Any] = []

    class FakeEmitter:
        def __init__(self, *, gms_server: str, token: str | None) -> None:
            assert gms_server == "http://localhost:8080"
            assert token is None

        def test_connection(self) -> None:
            return None

        def emit_mcp(self, proposal: Any) -> None:
            if hasattr(proposal, "to_obj"):
                proposal.to_obj()
            emitted.append(proposal)

    monkeypatch.setattr(rest_emitter, "DatahubRestEmitter", FakeEmitter)
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8080")
    monkeypatch.delenv("DATAHUB_GMS_TOKEN", raising=False)

    output = tmp_path / "manifest.json"
    manifest = _load_script().load_graph(output=output)

    assert manifest["status"] == "loaded"
    assert manifest["model_urn"].startswith("urn:li:mlModel:")
    assert manifest["deployment_urn"].startswith("urn:li:mlModelDeployment:")
    assert manifest["monthly_spend_feature_urn"].startswith("urn:li:mlFeature:")
    assert len(emitted) == len(manifest["emitted"])

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["expected_path"][-1] == manifest["deployment_urn"]
