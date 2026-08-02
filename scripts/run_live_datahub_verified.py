#!/usr/bin/env python3
# Run the definitive live verification with canonical MCP deployment matching.
"""Verify live DataHub evidence with strict deployment identity matching."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

import run_live_datahub_final as final

_DEPLOYMENT_URN = re.compile(
    r"^urn:li:mlModelDeployment:\(urn:li:dataPlatform:([^,]+),(.+),([^,)]+)\)$",
    re.IGNORECASE,
)


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _clean_urn(value: Any) -> str:
    text = unquote(str(value or "")).strip().strip("\"'")
    return text.rstrip(",.;")


def _platform_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("platform") or value.get("urn")
    text = str(value or "")
    marker = "urn:li:dataPlatform:"
    if marker in text:
        text = text.split(marker, 1)[1].split(",", 1)[0].split(")", 1)[0]
    return _token(text)


def _urn_identity(urn: Any) -> dict[str, str]:
    cleaned = _clean_urn(urn)
    match = _DEPLOYMENT_URN.match(cleaned)
    if not match:
        return {
            "urn": cleaned,
            "entity_type": "",
            "platform": "",
            "name": "",
            "environment": "",
        }
    platform, name, environment = match.groups()
    return {
        "urn": cleaned,
        "entity_type": "mlmodeldeployment",
        "platform": _token(platform),
        "name": _token(name),
        "environment": _token(environment),
    }


def _candidate_identities(value: Any, *, path: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    def visit(item: Any, location: str) -> None:
        if isinstance(item, dict):
            entity = item.get("entity") if isinstance(item.get("entity"), dict) else {}
            urn = item.get("urn") or entity.get("urn")
            entity_type = (
                item.get("entity_type")
                or item.get("entityType")
                or item.get("type")
                or entity.get("entity_type")
                or entity.get("entityType")
                or entity.get("type")
            )
            name = (
                item.get("name")
                or item.get("display_name")
                or item.get("displayName")
                or entity.get("name")
                or entity.get("display_name")
                or entity.get("displayName")
            )
            platform = item.get("platform") or entity.get("platform")

            if urn or entity_type or name:
                parsed = _urn_identity(urn)
                candidates.append(
                    {
                        "path": location,
                        "urn": parsed["urn"],
                        "entity_type": _token(entity_type)
                        or parsed["entity_type"],
                        "platform": _platform_name(platform)
                        or parsed["platform"],
                        "name": _token(name) or parsed["name"],
                        "environment": parsed["environment"],
                    }
                )

            for key, nested in item.items():
                visit(nested, f"{location}.{key}")
            return

        if isinstance(item, (list, tuple, set)):
            for index, nested in enumerate(item):
                visit(nested, f"{location}[{index}]")
            return

        if isinstance(item, str) and "urn:li:mlModelDeployment:" in item:
            parsed = _urn_identity(item)
            candidates.append({"path": location, **parsed})

    visit(value, path)

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for candidate in candidates:
        key = (
            candidate["path"],
            candidate["urn"],
            candidate["entity_type"],
            candidate["platform"],
            candidate["name"],
        )
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _matches(candidate: dict[str, str], expected: dict[str, str]) -> bool:
    if candidate["urn"] and candidate["urn"] == expected["urn"]:
        return True

    type_matches = candidate["entity_type"] == expected["entity_type"]
    name_matches = candidate["name"] == expected["name"]
    platform_matches = (
        not candidate["platform"]
        or not expected["platform"]
        or candidate["platform"] == expected["platform"]
    )
    environment_matches = (
        not candidate["environment"]
        or not expected["environment"]
        or candidate["environment"] == expected["environment"]
    )
    return type_matches and name_matches and platform_matches and environment_matches


def _model_deployment_evidence(
    *,
    model_snapshot: dict[str, Any],
    deployment_urn: str,
) -> dict[str, Any]:
    """Verify a deployment by exact URN or canonical type/name/platform identity."""

    expected = _urn_identity(deployment_urn)
    sections = {
        "model_entity_metadata": model_snapshot.get("entity") or {},
        "model_downstream": model_snapshot.get("downstream") or [],
        "provider_metadata": model_snapshot.get("provider_metadata") or {},
    }

    observed: list[dict[str, str]] = []
    matches: list[dict[str, str]] = []
    sources: list[str] = []
    for source, value in sections.items():
        candidates = _candidate_identities(value, path=source)
        observed.extend(candidates)
        source_matches = [candidate for candidate in candidates if _matches(candidate, expected)]
        if source_matches:
            sources.append(source)
            matches.extend(source_matches)

    return {
        "verified": bool(matches),
        "verification_sources": sources,
        "expected_identity": expected,
        "matched_candidates": matches,
        "observed_candidates": observed,
        "matching_rule": (
            "exact deployment URN, or ML model deployment entity type plus exact "
            "deployment name and compatible platform/environment"
        ),
    }


final._model_deployment_evidence = _model_deployment_evidence


if __name__ == "__main__":
    raise SystemExit(final.main())
