"""Tests for the ModelGuard command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.cli import main


def test_cli_returns_failure_and_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate",
            "--metric",
            "f1_score",
            "--baseline",
            "0.842",
            "--candidate",
            "0.771",
            "--max-regression",
            "0.02",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["metric"] == "f1_score"
    assert payload["change"] == -0.071
    assert payload["regression_amount"] == 0.071


def test_cli_returns_success_within_tolerance() -> None:
    exit_code = main(
        [
            "evaluate",
            "--metric",
            "f1_score",
            "--baseline",
            "0.842",
            "--candidate",
            "0.833",
            "--max-regression",
            "0.02",
        ]
    )

    assert exit_code == 0
