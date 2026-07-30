# Test the resilient DataHub startup wrapper without contacting Docker
# or a live DataHub instance.
"""Tests for the complete live DataHub startup wrapper."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> Any:
    path = ROOT / "scripts/run_live_datahub_complete.py"
    spec = importlib.util.spec_from_file_location("run_live_datahub_complete", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_url_and_gms_endpoints() -> None:
    module = _load_script()

    assert module._is_local_url("http://localhost:8080") is True
    assert module._is_local_url("http://127.0.0.1:8080") is True
    assert module._is_local_url("https://tenant.acryl.io") is False
    assert module._gms_endpoints("http://localhost:8080/") == (
        "http://localhost:8080/health",
        "http://localhost:8080/config",
    )


def test_existing_gms_skips_quickstart(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script()
    started: list[bool] = []

    monkeypatch.setattr(module, "_gms_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "_start_quickstart",
        lambda **_kwargs: started.append(True),
    )

    module._ensure_datahub(
        env={"DATAHUB_GMS_URL": "http://localhost:8080"},
        start_local=True,
        version=None,
        timeout_seconds=30,
    )

    assert started == []


def test_offline_local_gms_starts_quickstart(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script()
    events: list[str] = []

    monkeypatch.setattr(module, "_gms_ready", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        module,
        "_start_quickstart",
        lambda **_kwargs: events.append("start"),
    )
    monkeypatch.setattr(
        module,
        "_wait_for_gms",
        lambda *_args, **_kwargs: events.append("wait"),
    )

    module._ensure_datahub(
        env={"DATAHUB_GMS_URL": "http://localhost:8080"},
        start_local=True,
        version="stable",
        timeout_seconds=30,
    )

    assert events == ["start", "wait"]


def test_offline_remote_gms_is_never_started(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script()
    monkeypatch.setattr(module, "_gms_ready", lambda *_args, **_kwargs: False)

    with pytest.raises(RuntimeError, match="remote DataHub GMS is unreachable"):
        module._ensure_datahub(
            env={"DATAHUB_GMS_URL": "https://tenant.acryl.io"},
            start_local=True,
            version=None,
            timeout_seconds=30,
        )


def test_evidence_command_forwards_selected_options() -> None:
    module = _load_script()
    args = argparse.Namespace(
        install_mcp_server=True,
        promote=True,
        external_mcp=False,
        mcp_url="http://127.0.0.1:8000/mcp",
        mcp_health_url="http://127.0.0.1:8000/health",
    )

    command = module._evidence_command(args)

    assert command[:2] == [module.sys.executable, "scripts/run_live_datahub_evidence.py"]
    assert "--install-mcp-server" in command
    assert "--promote" in command
    assert "--external-mcp" not in command
    assert command[-4:] == [
        "--mcp-url",
        "http://127.0.0.1:8000/mcp",
        "--mcp-health-url",
        "http://127.0.0.1:8000/health",
    ]
