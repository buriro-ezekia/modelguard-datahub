import json
from pathlib import Path

import pytest

from modelguard.context.base import DataHubContextError
from modelguard.context.fixture import FixtureContextProvider


def _write_fixture(path: Path) -> str:
    urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,test.table,PROD)"
    path.write_text(
        json.dumps(
            {
                "source_urn": urn,
                "provider": "fixture",
                "generated_at": "2026-07-24T00:00:00+00:00",
                "entity": {"urn": urn, "name": "table"},
                "upstream": [
                    {"urn": "urn:li:dataset:one", "direction": "upstream", "hops": 1},
                    {"urn": "urn:li:dataset:two", "direction": "upstream", "hops": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    return urn


def test_fixture_provider_filters_direction_and_hops(tmp_path: Path) -> None:
    fixture = tmp_path / "context.json"
    urn = _write_fixture(fixture)
    provider = FixtureContextProvider(fixture)

    snapshot = provider.collect(
        source_urn=urn,
        source_column=None,
        direction="upstream",
        max_hops=1,
        max_results=10,
        schema_limit=10,
    )

    assert [item.urn for item in snapshot.upstream] == ["urn:li:dataset:one"]
    assert snapshot.downstream == ()


def test_fixture_provider_rejects_wrong_urn(tmp_path: Path) -> None:
    fixture = tmp_path / "context.json"
    _write_fixture(fixture)
    provider = FixtureContextProvider(fixture)

    with pytest.raises(DataHubContextError, match="mismatch"):
        provider.collect(
            source_urn="urn:li:dataset:wrong",
            source_column=None,
            direction="both",
            max_hops=3,
            max_results=10,
            schema_limit=10,
        )
