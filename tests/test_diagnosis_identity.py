"""Tests for stable Phase 3 case identity."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.diagnosis import ChangeSet
from modelguard.diagnosis.identity import diagnosis_id
from modelguard.models import ContextSnapshot


def test_diagnosis_id_ignores_collection_timestamp_and_provider_metadata() -> None:
    evaluation = json.loads(
        Path("examples/evaluation_failed.json").read_text(encoding="utf-8")
    )
    context_payload = json.loads(
        Path("examples/context_snapshot.json").read_text(encoding="utf-8")
    )
    changes = ChangeSet.from_dict(
        json.loads(Path("examples/regression_case.json").read_text(encoding="utf-8"))
    )

    first = ContextSnapshot.from_dict(context_payload)
    context_payload["generated_at"] = "2030-01-01T00:00:00+00:00"
    context_payload["provider_metadata"] = {"request_id": "different"}
    second = ContextSnapshot.from_dict(context_payload)

    assert diagnosis_id(evaluation, first, changes) == diagnosis_id(
        evaluation,
        second,
        changes,
    )
