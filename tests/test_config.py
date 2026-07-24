from pathlib import Path

import pytest

from modelguard.config import ConfigurationError, load_config


def test_load_config_resolves_fixture_relative_to_config(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "modelguard.yml"
    config_path.write_text(
        """
project:
  name: test-project
model:
  urn: urn:li:mlModel:test

datahub:
  provider: fixture
  fixture_path: fixture.json
  max_hops: 2
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project_name == "test-project"
    assert config.datahub.fixture_path == fixture.resolve()
    assert config.datahub.max_hops == 2


def test_environment_overrides_provider_and_urls(tmp_path: Path) -> None:
    config_path = tmp_path / "modelguard.yml"
    config_path.write_text(
        "project: {name: test}\nmodel: {urn: 'urn:li:mlModel:test'}\ndatahub: {}\n",
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        environ={
            "MODELGUARD_DATAHUB_PROVIDER": "mcp",
            "DATAHUB_GMS_URL": "http://gms:8080",
            "DATAHUB_MCP_URL": "http://gms:8080/mcp",
        },
    )

    assert config.datahub.provider == "mcp"
    assert config.datahub.gms_url == "http://gms:8080"
    assert config.datahub.mcp_url == "http://gms:8080/mcp"


def test_invalid_max_hops_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "modelguard.yml"
    config_path.write_text(
        "project: {name: test}\nmodel: {urn: test}\ndatahub: {max_hops: 0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_config(config_path)
