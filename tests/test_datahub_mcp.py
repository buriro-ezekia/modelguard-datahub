"""Tests for the DataHub MCP context provider."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from modelguard.context.base import DataHubContextError
from modelguard.context.datahub_mcp import (
    DataHubMcpContextProvider,
    _decode_tool_result,
    _extract_urns,
)


class FakeToolCaller:
    def __init__(self, tools: set[str] | None = None) -> None:
        self.tools = tools or {"get_entities", "list_schema_fields", "get_lineage"}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> set[str]:
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if name == "get_entities":
            return {
                "urn": arguments["urns"],
                "type": "MLMODEL",
                "name": "model",
            }
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
                key: {
                    "searchResults": [
                        {
                            "entity": {
                                "urn": f"urn:li:dataset:{key}",
                                "type": "DATASET",
                                "name": key,
                                "platform": "snowflake",
                            },
                            "degree": 1,
                        }
                    ],
                    "returned": 1,
                    "hasMore": False,
                }
            }
        raise AssertionError(name)


class WrappedDeploymentToolCaller(FakeToolCaller):
    deployment_urn = (
        "urn:li:mlModelDeployment:(urn:li:dataPlatform:kserve,churn-api-prod,PROD)"
    )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if name == "get_entities":
            return {
                "result": json.dumps(
                    {
                        "urn": arguments["urns"],
                        "type": "MLMODEL",
                        "name": "churn-model-v3",
                        "deployments": [self.deployment_urn],
                    }
                )
            }
        if name == "list_schema_fields":
            return {"result": {"fields": []}}
        if name == "get_lineage":
            key = "upstreams" if arguments["upstream"] else "downstreams"
            urn = (
                "urn:li:dataset:(urn:li:dataPlatform:snowflake,training.churn,PROD)"
                if arguments["upstream"]
                else self.deployment_urn
            )
            return {
                "result": {
                    key: {
                        "searchResults": [
                            {
                                "entity": {"urn": urn, "type": "ML_MODEL_DEPLOYMENT"},
                                "degree": 1,
                            }
                        ]
                    }
                }
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


def test_mcp_provider_preserves_deployment_urns_from_wrapped_payloads() -> None:
    caller = WrappedDeploymentToolCaller()
    provider = DataHubMcpContextProvider(tool_caller=caller)

    snapshot = provider.collect(
        source_urn="urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)",
        source_column=None,
        direction="both",
        max_hops=3,
        max_results=25,
        schema_limit=40,
    )

    assert snapshot.downstream[0].urn == caller.deployment_urn
    assert caller.deployment_urn in snapshot.provider_metadata["entity_urns"]
    assert caller.deployment_urn in snapshot.provider_metadata["downstream_urns"]


def test_mcp_decoder_unwraps_structured_result_envelope() -> None:
    payload = {
        "downstreams": {
            "searchResults": [
                {
                    "entity": {
                        "urn": "urn:li:mlModelDeployment:(urn:li:dataPlatform:kserve,api,PROD)"
                    }
                }
            ]
        }
    }
    result = SimpleNamespace(isError=False, structuredContent={"result": payload})

    assert _decode_tool_result(result) == payload
    assert "urn:li:mlModelDeployment:(urn:li:dataPlatform:kserve,api,PROD)" in (
        _extract_urns({"result": json.dumps(payload)})
    )


def test_mcp_provider_reports_missing_required_tools() -> None:
    provider = DataHubMcpContextProvider(tool_caller=FakeToolCaller({"get_entities"}))

    with pytest.raises(DataHubContextError, match="missing required tools"):
        provider.test_connection()
