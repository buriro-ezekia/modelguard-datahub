from dataclasses import dataclass

from modelguard.context.datahub_sdk import DataHubSdkContextProvider


@dataclass
class FakeLineage:
    urn: str
    type: str
    hops: int
    direction: str
    platform: str
    name: str


class FakeEntities:
    def get(self, urn: str) -> dict[str, object]:
        return {
            "urn": urn,
            "type": "MLMODEL",
            "name": "churn-model-v3",
            "owners": [{"urn": "urn:li:corpGroup:data-platform"}],
            "schemaMetadata": {
                "fields": [
                    {"fieldPath": "monthly_spend", "nativeDataType": "DOUBLE"}
                ]
            },
        }


class FakeLineageClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_lineage(self, **kwargs: object) -> list[FakeLineage]:
        self.calls.append(kwargs)
        direction = str(kwargs["direction"])
        return [
            FakeLineage(
                urn=f"urn:li:dataset:{direction}",
                type="DATASET",
                hops=1,
                direction=direction,
                platform="snowflake",
                name=direction,
            )
        ]


class FakeClient:
    def __init__(self) -> None:
        self.entities = FakeEntities()
        self.lineage = FakeLineageClient()
        self.checked = False

    def test_connection(self) -> None:
        self.checked = True


def test_sdk_provider_collects_entity_schema_and_both_lineage_directions() -> None:
    client = FakeClient()
    provider = DataHubSdkContextProvider(client=client)

    provider.test_connection()
    snapshot = provider.collect(
        source_urn="urn:li:mlModel:test",
        source_column="monthly_spend",
        direction="both",
        max_hops=3,
        max_results=50,
        schema_limit=100,
    )

    assert client.checked is True
    assert snapshot.provider == "sdk"
    assert snapshot.entity.schema_fields[0].field_path == "monthly_spend"
    assert snapshot.upstream[0].urn == "urn:li:dataset:upstream"
    assert snapshot.downstream[0].urn == "urn:li:dataset:downstream"
    assert client.lineage.calls[0]["source_column"] == "monthly_spend"
    assert client.lineage.calls[0]["count"] == 50
