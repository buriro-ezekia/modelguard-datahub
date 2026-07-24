"""Stable identity generation for diagnosis cases."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from modelguard.diagnosis.hypotheses import ChangeSet
from modelguard.models import ContextSnapshot


def diagnosis_id(
    evaluation: dict[str, Any],
    context: ContextSnapshot,
    changes: ChangeSet,
) -> str:
    """Return an ID unaffected by collection time or provider request metadata."""
    context_payload = context.to_dict()
    context_payload.pop("generated_at", None)
    context_payload.pop("provider_metadata", None)
    payload = {
        "evaluation": evaluation,
        "context": context_payload,
        "changes": changes.to_dict(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"diag-{digest}"
