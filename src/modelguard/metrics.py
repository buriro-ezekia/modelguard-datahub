"""Deterministic model-metric regression evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

MetricDirection = Literal["higher_is_better", "lower_is_better"]
_SERIALISATION_SIGNIFICANT_DIGITS = 12


def _normalise_for_serialisation(value: float) -> float:
    """Remove insignificant binary floating-point noise from JSON values."""
    normalised = float(f"{value:.{_SERIALISATION_SIGNIFICANT_DIGITS}g}")
    return 0.0 if normalised == 0 else normalised


@dataclass(frozen=True, slots=True)
class MetricPolicy:
    """Policy defining when a candidate metric counts as a regression."""

    metric: str
    maximum_allowed_regression: float
    direction: MetricDirection = "higher_is_better"

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric must not be empty")
        if not math.isfinite(self.maximum_allowed_regression):
            raise ValueError("maximum_allowed_regression must be finite")
        if self.maximum_allowed_regression < 0:
            raise ValueError("maximum_allowed_regression must be non-negative")
        if self.direction not in {"higher_is_better", "lower_is_better"}:
            raise ValueError(f"unsupported metric direction: {self.direction}")


@dataclass(frozen=True, slots=True)
class MetricEvaluation:
    """Comparison between an approved baseline and a candidate result."""

    policy: MetricPolicy
    baseline: float
    candidate: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.baseline):
            raise ValueError("baseline must be finite")
        if not math.isfinite(self.candidate):
            raise ValueError("candidate must be finite")

    @property
    def change(self) -> float:
        """Return candidate minus baseline."""
        return self.candidate - self.baseline

    @property
    def regression_amount(self) -> float:
        """Return the adverse change, or zero when the metric improved."""
        if self.policy.direction == "higher_is_better":
            return max(0.0, self.baseline - self.candidate)
        return max(0.0, self.candidate - self.baseline)

    @property
    def failed(self) -> bool:
        """Return whether the adverse change exceeds the configured tolerance."""
        tolerance = self.policy.maximum_allowed_regression
        return self.regression_amount > tolerance and not math.isclose(
            self.regression_amount,
            tolerance,
            rel_tol=1e-12,
            abs_tol=1e-15,
        )

    @property
    def status(self) -> Literal["passed", "failed"]:
        return "failed" if self.failed else "passed"

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serialisable representation."""
        return {
            "metric": self.policy.metric,
            "direction": self.policy.direction,
            "baseline": _normalise_for_serialisation(self.baseline),
            "candidate": _normalise_for_serialisation(self.candidate),
            "change": _normalise_for_serialisation(self.change),
            "regression_amount": _normalise_for_serialisation(self.regression_amount),
            "maximum_allowed_regression": _normalise_for_serialisation(
                self.policy.maximum_allowed_regression
            ),
            "status": self.status,
        }
