"""Regression tests for DataHub GraphQL operation contracts."""

from modelguard.reporting.datahub_writer import _RESOLVE_MUTATION


def test_resolve_mutation_uses_datahub_incident_status_input() -> None:
    """Keep the variable type aligned with DataHub's updateIncidentStatus schema."""
    assert "$input: IncidentStatusInput!" in _RESOLVE_MUTATION
    assert "UpdateIncidentStatusInput!" not in _RESOLVE_MUTATION
