"""Tests for deterministic regression evaluation."""

from __future__ import annotations

import pytest

from modelguard.metrics import MetricEvaluation, MetricPolicy


def test_higher_is_better_metric_fails_beyond_tolerance() -> None:
    evaluation = MetricEvaluation(
        policy=MetricPolicy("f1_score", maximum_allowed_regression=0.02),
        baseline=0.842,
        candidate=0.771,
    )

    assert evaluation.failed is True
    assert evaluation.status == "failed"
    assert evaluation.regression_amount == pytest.approx(0.071)


def test_higher_is_better_metric_passes_at_boundary() -> None:
    evaluation = MetricEvaluation(
        policy=MetricPolicy("f1_score", maximum_allowed_regression=0.02),
        baseline=0.84,
        candidate=0.82,
    )

    assert evaluation.failed is False
    assert evaluation.status == "passed"


def test_lower_is_better_metric_detects_increased_error() -> None:
    evaluation = MetricEvaluation(
        policy=MetricPolicy(
            "rmse",
            maximum_allowed_regression=0.5,
            direction="lower_is_better",
        ),
        baseline=2.0,
        candidate=2.8,
    )

    assert evaluation.failed is True
    assert evaluation.regression_amount == pytest.approx(0.8)


def test_improvement_never_counts_as_regression() -> None:
    evaluation = MetricEvaluation(
        policy=MetricPolicy("f1_score", maximum_allowed_regression=0.0),
        baseline=0.80,
        candidate=0.85,
    )

    assert evaluation.failed is False
    assert evaluation.regression_amount == 0.0


def test_serialised_values_remove_binary_floating_point_noise() -> None:
    evaluation = MetricEvaluation(
        policy=MetricPolicy("f1_score", maximum_allowed_regression=0.02),
        baseline=0.842,
        candidate=0.771,
    )

    payload = evaluation.to_dict()

    assert payload["change"] == -0.071
    assert payload["regression_amount"] == 0.071


@pytest.mark.parametrize("value", [-0.01, float("inf"), float("nan")])
def test_invalid_policy_thresholds_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        MetricPolicy("f1_score", maximum_allowed_regression=value)


@pytest.mark.parametrize("baseline,candidate", [(float("nan"), 0.8), (0.8, float("inf"))])
def test_non_finite_metric_values_are_rejected(baseline: float, candidate: float) -> None:
    with pytest.raises(ValueError):
        MetricEvaluation(
            policy=MetricPolicy("f1_score", maximum_allowed_regression=0.02),
            baseline=baseline,
            candidate=candidate,
        )
