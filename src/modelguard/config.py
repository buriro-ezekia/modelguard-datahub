"""Configuration loading for ModelGuard."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from modelguard.models import ContextProviderName


class ConfigurationError(ValueError):
    """Raised when ModelGuard configuration is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class DataHubSettings:
    """Connection and context-retrieval settings without embedded secrets."""

    provider: ContextProviderName = "fixture"
    gms_url: str | None = None
    mcp_url: str | None = None
    token_env: str = "DATAHUB_GMS_TOKEN"
    mcp_token_env: str = "DATAHUB_MCP_TOKEN"
    fixture_path: Path = Path("examples/datahub_context_fixture.json")
    max_hops: int = 3
    max_results: int = 100
    schema_limit: int = 200
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.provider not in {"fixture", "sdk", "mcp"}:
            raise ConfigurationError(f"unsupported DataHub provider: {self.provider}")
        if self.max_hops < 1:
            raise ConfigurationError("datahub.max_hops must be at least 1")
        if self.max_results < 1:
            raise ConfigurationError("datahub.max_results must be at least 1")
        if self.schema_limit < 1:
            raise ConfigurationError("datahub.schema_limit must be at least 1")
        if self.timeout_seconds <= 0:
            raise ConfigurationError("datahub.timeout_seconds must be positive")

    def token(self, environ: Mapping[str, str] | None = None) -> str | None:
        values = environ or os.environ
        return values.get(self.token_env)

    def mcp_token(self, environ: Mapping[str, str] | None = None) -> str | None:
        values = environ or os.environ
        return values.get(self.mcp_token_env) or values.get(self.token_env)


@dataclass(frozen=True, slots=True)
class ModelGuardConfig:
    """Top-level application configuration."""

    project_name: str
    model_urn: str
    datahub: DataHubSettings

    def with_provider(self, provider: ContextProviderName | None) -> ModelGuardConfig:
        if provider is None:
            return self
        return replace(self, datahub=replace(self.datahub, provider=provider))


def load_config(
    path: str | Path = "config/modelguard.yml",
    *,
    environ: Mapping[str, str] | None = None,
) -> ModelGuardConfig:
    """Load YAML configuration and apply safe environment overrides."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(f"configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigurationError("configuration root must be a mapping")

    project = _mapping(raw.get("project"), "project")
    model = _mapping(raw.get("model"), "model")
    datahub = _mapping(raw.get("datahub"), "datahub")
    env = environ or os.environ

    provider = env.get("MODELGUARD_DATAHUB_PROVIDER", datahub.get("provider", "fixture"))
    gms_url = env.get("DATAHUB_GMS_URL") or _optional_string(datahub.get("gms_url"))
    mcp_url = env.get("DATAHUB_MCP_URL") or _optional_string(datahub.get("mcp_url"))

    settings = DataHubSettings(
        provider=provider,
        gms_url=gms_url,
        mcp_url=mcp_url,
        token_env=str(datahub.get("token_env", "DATAHUB_GMS_TOKEN")),
        mcp_token_env=str(datahub.get("mcp_token_env", "DATAHUB_MCP_TOKEN")),
        fixture_path=_resolve_path(
            config_path,
            datahub.get("fixture_path", "../examples/datahub_context_fixture.json"),
        ),
        max_hops=int(datahub.get("max_hops", 3)),
        max_results=int(datahub.get("max_results", 100)),
        schema_limit=int(datahub.get("schema_limit", 200)),
        timeout_seconds=float(datahub.get("timeout_seconds", 30.0)),
    )

    project_name = str(project.get("name") or "modelguard-datahub").strip()
    model_urn = str(model.get("urn") or "").strip()
    if not project_name:
        raise ConfigurationError("project.name must not be empty")
    if not model_urn:
        raise ConfigurationError("model.urn must not be empty")

    return ModelGuardConfig(project_name=project_name, model_urn=model_urn, datahub=settings)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def _resolve_path(config_path: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
