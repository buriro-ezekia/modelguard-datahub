from modelguard.models import ContextSnapshot, EntityContext


def test_context_snapshot_round_trip() -> None:
    snapshot = ContextSnapshot(
        source_urn="urn:li:dataset:test",
        provider="fixture",
        generated_at="2026-07-24T00:00:00+00:00",
        entity=EntityContext(urn="urn:li:dataset:test", name="test"),
        max_hops=2,
    )

    restored = ContextSnapshot.from_dict(snapshot.to_dict())

    assert restored == snapshot
