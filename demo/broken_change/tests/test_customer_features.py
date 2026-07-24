"""Targeted regression tests for the monthly-spend transformation."""

from features.customer_features import calculate_monthly_spend


def test_positive_account_age() -> None:
    assert calculate_monthly_spend(120.0, 12) == 10.0


def test_zero_account_age_uses_safe_fallback() -> None:
    assert calculate_monthly_spend(40.0, 0) == 0.0


def test_negative_account_age_uses_safe_fallback() -> None:
    assert calculate_monthly_spend(40.0, -1) == 0.0
