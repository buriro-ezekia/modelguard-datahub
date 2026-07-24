import os

import pytest

from modelguard.config import load_config
from modelguard.context import build_context_provider
from modelguard.orchestrator import ContextCollector


@pytest.mark.live_datahub
def test_live_datahub_context_when_explicitly_enabled() -> None:
    if os.environ.get("MODELGUARD_LIVE_DATAHUB") != "1":
        pytest.skip("set MODELGUARD_LIVE_DATAHUB=1 to run live DataHub verification")

    provider_name = os.environ.get("MODELGUARD_DATAHUB_PROVIDER", "sdk")
    config = load_config().with_provider(provider_name)
    provider = build_context_provider(config.datahub)
    collector = ContextCollector(config=config, provider=provider)

    collector.check()
    snapshot = collector.collect(direction="both")

    assert snapshot.source_urn == config.model_urn
    assert snapshot.entity.urn == config.model_urn
