# Test SDK and MCP fallback behaviour for entity types without detail support.
"""Contract tests for lineage-only DataHub entities such as model deployments."""

from __future__ import annotations

from typing import Any

from modelguard.context.base import DataHubContextError
from modelguard.context.datahub_mcp import DataHubMcpContextProvider
from modelguard.context.datahub_sdk import DataHubSdkContextProvider

MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)"
DEPLOYMENT_URN = (
    "urn:li:mlModelDeployment:(urn:li:dataPlatform:kserve,churn-api-prod,PROD)"
)


class UnsupportedEntities:
    def get(self, urn: str) -> Any:
        raise ValueError("Entity type mlModelDeployment is not yet supported")


class DeploymentLineageClient:
    def get_lineage(self, **kwargs: Any) -> list[dict[str, Any]]:
        if kwargs["direction"] == "upstream":
            return [{"urn": MODEL_URN, "type": "MLMODEL", "hops": 1}]
        return []


class SdkClient:
    def __init__(self) -> None:
        self.entities = UnsupportedEntities()
        self.lineage = DeploymentLineageClient()


class McpCaller:
    def list_tools(self) -> set[str]:
        return {"get_entities", "list_schema_fields", "get_lineage"}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name in {"get_entities", "list_schema_fields"}:
            raise DataHubContextError(
                "Entity type mlModelDeployment is not yet supported"
            )
        if name == "get_lineage":
            key = "upstreams" if arguments["upstream"] else "downstreams"
            results = (
                [{"entity": {"urn": MODEL_URN, "type": "MLMODEL"}, "degree": 1}]
                if arguments["upstream"]
                else []
            )
            return {key: {"searchResults": results}}
        raise AssertionError(name)


def test_sdk_collects_lineage_when_entity_registry_lacks_deployment_type() -> None:
    snapshot = DataHubSdkContextProvider(client=SdkClient()).collect(
        source_urn=DEPLOYMENT_URN,
        source_column=None,
        direction="both",
        max_hops=3,
        max_results=30,
        schema_limit=100,
    )

    assert snapshot.entity.urn == DEPLOYMENT_URN
    assert snapshot.entity.entity_type == "MLMODELDEPLOYMENT"
    assert snapshot.upstream[0].urn == MODEL_URN
    assert snapshot.provider_metadata["entity_details_available"] is False
    assert snapshot.provider_metadata["warnings"]


def test_mcp_collects_lineage_when_metadata_tools_lack_deployment_type() -> None:
    snapshot = DataHubMcpContextProvider(tool_caller=McpCaller()).collect(
        source_urn=DEPLOYMENT_URN,
        source_column=None,
        direction="both",
        max_hops=3,
        max_results=30,
        schema_limit=100,
    )

    assert snapshot.entity.urn == DEPLOYMENT_URN
    assert snapshot.entity.entity_type == "MLMODELDEPLOYMENT"
    assert snapshot.upstream[0].urn == MODEL_URN
    assert snapshot.provider_metadata["entity_details_available"] is False
    assert len(snapshot.provider_metadata["warnings"]) == 2
