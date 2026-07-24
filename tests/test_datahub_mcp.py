from typing import Any

import pytest

from modelguard.context.base import DataHubContextError
from modelguard.context.datahub_mcp import DataHubMcpContextProvider


class FakeToolCaller:
    def __init__(self, tools: set[str] | None = None) -> None:
        self.tools = tools or {"get_entities", "list_schema_fields", "get_lineage"}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> set[str]:
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if name == "get_entities":
            return {"urn": arguments["urns"], "type": "MLMODEL", "name": "model"}
        if name == "list_schema_fields":
            return {
                "urn": arguments["urn"],
                "fields": [
                    {"fieldPath": "monthly_spend", "nativeDataType": "DOUBLE"}
                ],
            }
        if name == "get_lineage":
            key = "upstreams" if arguments["upstream"] else "downstreams"
            return {
                key: [
                    {
                        "urn": f"urn:li:dataset:{key}",
                        "type": "DATASET",
                        "degree": 1,
                    }
                ]
            }
        raise AssertionError(name)


def test_mcp_provider_uses_official_tool_arguments() -> None:
    caller = FakeToolCaller()
    provider = DataHubMcpContextProvider(tool_caller=caller)

    provider.test_connection()
    snapshot = provider.collect(
        source_urn="urn:li:mlModel:test",
        source_column="monthly_spend",
        direction="both",
        max_hops=3,
        max_results=25,
        schema_limit=40,
    )

    assert snapshot.entity.schema_fields[0].field_path == "monthly_spend"
    assert snapshot.upstream[0].urn == "urn:li:dataset:upstreams"
    assert snapshot.downstream[0].urn == "urn:li:dataset:downstreams"
    assert caller.calls[0] == ("get_entities", {"urns": "urn:li:mlModel:test"})
    assert caller.calls[1][1] == {
        "urn": "urn:li:mlModel:test",
        "limit": 40,
        "offset": 0,
    }
    assert caller.calls[2][1]["upstream"] is True
    assert caller.calls[2][1]["max_results"] == 25


def test_mcp_provider_reports_missing_required_tools() -> None:
    provider = DataHubMcpContextProvider(tool_caller=FakeToolCaller({"get_entities"}))

    with pytest.raises(DataHubContextError, match="missing required tools"):
        provider.test_connection()
