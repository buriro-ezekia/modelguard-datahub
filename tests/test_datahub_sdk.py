"""Tests for the DataHub SDK context provider."""

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


class SlottedSchemaField:
    __slots__ = ("_field_path", "_native_type")

    def __init__(self, field_path: str, native_type: str) -> None:
        self._field_path = field_path
        self._native_type = native_type

    @property
    def field_path(self) -> str:
        return self._field_path

    @property
    def native_type(self) -> str:
        return self._native_type


class SlottedSchema:
    __slots__ = ("_fields",)

    def __init__(self) -> None:
        self._fields = [SlottedSchemaField("monthly_spend", "DOUBLE")]

    @property
    def fields(self) -> list[SlottedSchemaField]:
        return self._fields


class SlottedDataset:
    __slots__ = ("_urn", "_schema")

    def __init__(self, urn: str) -> None:
        self._urn = urn
        self._schema = SlottedSchema()

    @property
    def urn(self) -> str:
        return self._urn

    @property
    def display_name(self) -> str:
        return "customer_features"

    @property
    def description(self) -> str:
        return "Live feature dataset used by ModelGuard."

    @property
    def schema(self) -> SlottedSchema:
        return self._schema

    @property
    def owners(self) -> list[dict[str, str]]:
        return [{"urn": "urn:li:corpGroup:data-platform"}]

    @property
    def tags(self) -> list[dict[str, str]]:
        return [{"urn": "urn:li:tag:Production"}]


class SlottedEntities:
    def get(self, urn: str) -> SlottedDataset:
        return SlottedDataset(urn)


class SlottedClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.entities = SlottedEntities()


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


def test_sdk_provider_normalises_slotted_sdk_entities() -> None:
    source_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
        "modelguard.features.customer_features,PROD)"
    )
    provider = DataHubSdkContextProvider(client=SlottedClient())

    snapshot = provider.collect(
        source_urn=source_urn,
        source_column=None,
        direction="both",
        max_hops=3,
        max_results=50,
        schema_limit=100,
    )

    assert snapshot.entity.urn == source_urn
    assert snapshot.entity.entity_type == "DATASET"
    assert snapshot.entity.name == "customer_features"
    assert snapshot.entity.platform == "snowflake"
    assert snapshot.entity.description == "Live feature dataset used by ModelGuard."
    assert snapshot.entity.owners == ("urn:li:corpGroup:data-platform",)
    assert snapshot.entity.tags == ("urn:li:tag:Production",)
    assert snapshot.entity.schema_fields[0].field_path == "monthly_spend"
    assert snapshot.entity.schema_fields[0].native_type == "DOUBLE"
