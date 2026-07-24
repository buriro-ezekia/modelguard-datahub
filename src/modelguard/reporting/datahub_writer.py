"""Safe DataHub incident lifecycle write-back."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib import error, request

if TYPE_CHECKING:
    from modelguard.reporting.publication import ChannelReceipt, PublicationPlan

GraphQLTransport = Callable[
    [str, dict[str, Any], str, dict[str, str]],
    dict[str, Any],
]

_INCIDENT_QUERY = """
query ModelGuardIncidents($urn: String!, $state: IncidentState!) {
  dataset(urn: $urn) {
    incidents(state: $state, start: 0, count: 100) {
      incidents {
        urn
        title
        description
        status {
          state
        }
      }
    }
  }
}
""".strip()

_RAISE_MUTATION = """
mutation RaiseModelGuardIncident($input: RaiseIncidentInput!) {
  raiseIncident(input: $input)
}
""".strip()

_RESOLVE_MUTATION = """
mutation ResolveModelGuardIncident(
  $urn: String!,
  $input: UpdateIncidentStatusInput!
) {
  updateIncidentStatus(urn: $urn, input: $input)
}
""".strip()


class DataHubIncidentWriter:
    """Raise and resolve one idempotent DataHub incident for a validated repair."""

    def __init__(
        self,
        *,
        mode: str = "fixture",
        graphql_url: str | None = None,
        token: str | None = None,
        fixture_state: Path | None = None,
        transport: GraphQLTransport | None = None,
    ) -> None:
        if mode not in {"off", "fixture", "live"}:
            raise ValueError(f"unsupported DataHub publication mode: {mode}")
        self.mode = mode
        self.graphql_url = graphql_url or _default_graphql_url()
        self.token = token or os.getenv("DATAHUB_GRAPHQL_TOKEN") or os.getenv(
            "DATAHUB_GMS_TOKEN"
        )
        self.fixture_state = fixture_state
        self.transport = transport or _graphql_request

    def publish(self, plan: PublicationPlan, *, apply: bool) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        if self.mode == "off":
            return ChannelReceipt(
                channel="datahub",
                mode="off",
                status="skipped",
                action="disabled",
            )
        if not apply:
            return ChannelReceipt(
                channel="datahub",
                mode=self.mode,
                status="planned",
                action="raise_and_resolve_incident",
                details={
                    "asset_urn": plan.datahub_asset_urn,
                    "incident_type": "CUSTOM",
                },
            )
        try:
            if self.mode == "fixture":
                return self._publish_fixture(plan)
            return self._publish_live(plan)
        except Exception as exc:
            return ChannelReceipt(
                channel="datahub",
                mode=self.mode,
                status="failed",
                action="error",
                details={"warnings": [f"DataHub write-back failed: {exc}"]},
            )

    def _publish_fixture(self, plan: PublicationPlan) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        state_path = self.fixture_state or Path("artifacts/datahub_incident_state.json")
        state = _load_state(state_path, {"incidents": []})
        incidents = state.setdefault("incidents", [])
        existing = next(
            (item for item in incidents if item.get("delivery_id") == plan.delivery_id),
            None,
        )
        if existing is None:
            incident_urn = (
                "urn:li:incident:modelguard-"
                f"{plan.delivery_id.removeprefix('delivery-')}"
            )
            existing = {
                "delivery_id": plan.delivery_id,
                "urn": incident_urn,
                "resource_urn": plan.datahub_asset_urn,
                "type": "CUSTOM",
                "custom_type": "ModelGuard",
                "title": plan.datahub_incident_title,
                "description": plan.datahub_incident_description,
                "state": "RESOLVED",
                "resolution_message": plan.datahub_resolution_message,
            }
            incidents.append(existing)
            action = "raised_and_resolved"
        elif existing.get("state") == "RESOLVED":
            action = "noop"
        else:
            existing["state"] = "RESOLVED"
            existing["resolution_message"] = plan.datahub_resolution_message
            action = "resolved"
        _save_state(state_path, state)
        return ChannelReceipt(
            channel="datahub",
            mode="fixture",
            status="noop" if action == "noop" else "published",
            action=action,
            external_id=str(existing["urn"]),
            details={
                "asset_urn": plan.datahub_asset_urn,
                "state_path": str(state_path),
                "incident_state": "RESOLVED",
            },
        )

    def _publish_live(self, plan: PublicationPlan) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        if not self.graphql_url:
            raise RuntimeError("DATAHUB_GRAPHQL_URL or DATAHUB_GMS_URL is required")
        if not self.token:
            raise RuntimeError(
                "DATAHUB_GRAPHQL_TOKEN or DATAHUB_GMS_TOKEN is required"
            )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "modelguard-datahub",
        }
        existing = self._find_existing(plan, headers)
        if existing is not None and _incident_state(existing) == "RESOLVED":
            return ChannelReceipt(
                channel="datahub",
                mode="live",
                status="noop",
                action="noop",
                external_id=str(existing.get("urn")),
                details={"asset_urn": plan.datahub_asset_urn},
            )
        if existing is None:
            result = self.transport(
                _RAISE_MUTATION,
                {
                    "input": {
                        "resourceUrn": plan.datahub_asset_urn,
                        "type": "CUSTOM",
                        "customType": "ModelGuard",
                        "title": plan.datahub_incident_title,
                        "description": plan.datahub_incident_description,
                    }
                },
                self.graphql_url,
                headers,
            )
            incident_urn = _graphql_value(result, "raiseIncident")
            action = "raised_and_resolved"
        else:
            incident_urn = str(existing["urn"])
            action = "resolved"
        result = self.transport(
            _RESOLVE_MUTATION,
            {
                "urn": incident_urn,
                "input": {
                    "state": "RESOLVED",
                    "message": plan.datahub_resolution_message,
                },
            },
            self.graphql_url,
            headers,
        )
        resolved = _graphql_value(result, "updateIncidentStatus")
        if resolved not in {True, "true", "True", "1"}:
            raise RuntimeError("DataHub did not confirm incident resolution")
        return ChannelReceipt(
            channel="datahub",
            mode="live",
            status="published",
            action=action,
            external_id=incident_urn,
            details={
                "asset_urn": plan.datahub_asset_urn,
                "incident_state": "RESOLVED",
            },
        )

    def _find_existing(
        self,
        plan: PublicationPlan,
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        marker = f"[modelguard-delivery:{plan.delivery_id}]"
        for state in ("ACTIVE", "RESOLVED"):
            result = self.transport(
                _INCIDENT_QUERY,
                {"urn": plan.datahub_asset_urn, "state": state},
                str(self.graphql_url),
                headers,
            )
            data = result.get("data") if isinstance(result, dict) else None
            dataset = data.get("dataset") if isinstance(data, dict) else None
            incident_page = (
                dataset.get("incidents") if isinstance(dataset, dict) else None
            )
            incidents = (
                incident_page.get("incidents")
                if isinstance(incident_page, dict)
                else []
            )
            for incident in incidents or []:
                if (
                    isinstance(incident, dict)
                    and marker in str(incident.get("description") or "")
                ):
                    return incident
        return None


def _graphql_request(
    query: str,
    variables: dict[str, Any],
    url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        method="POST",
        headers=headers,
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
    except error.HTTPError as exc:
        message = exc.read().decode(errors="replace")
        raise RuntimeError(f"DataHub returned HTTP {exc.code}: {message[:500]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"DataHub request failed: {exc.reason}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DataHub returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("DataHub returned an invalid GraphQL response")
    if value.get("errors"):
        raise RuntimeError(f"DataHub GraphQL errors: {value['errors']}")
    return value


def _graphql_value(result: dict[str, Any], field: str) -> Any:
    data = result.get("data")
    if not isinstance(data, dict) or field not in data:
        raise RuntimeError(f"DataHub GraphQL response is missing {field}")
    return data[field]


def _incident_state(incident: dict[str, Any]) -> str | None:
    status = incident.get("status")
    if not isinstance(status, dict):
        return None
    value = status.get("state")
    return str(value) if value is not None else None


def _default_graphql_url() -> str | None:
    explicit = os.getenv("DATAHUB_GRAPHQL_URL")
    if explicit:
        return explicit
    gms = os.getenv("DATAHUB_GMS_URL")
    if not gms:
        return None
    return f"{gms.rstrip('/')}/api/graphql"


def _load_state(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read fixture state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"fixture state {path} must contain a JSON object")
    return value


def _save_state(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
