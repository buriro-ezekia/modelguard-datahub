"""Tests for the Phase 3 command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

from modelguard.cli import main


def test_diagnose_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    json_output = tmp_path / "diagnosis.json"
    markdown_output = tmp_path / "diagnosis.md"

    exit_code = main(
        [
            "diagnose",
            "--evaluation",
            "examples/evaluation_failed.json",
            "--context",
            "examples/context_snapshot.json",
            "--changes",
            "examples/regression_case.json",
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["status"] == "ranked"
    assert payload["top_hypothesis_id"] == "H001"
    assert payload["hypotheses"][0]["category"] == "feature_transformation"
    assert "ModelGuard Root-Cause Report" in markdown
