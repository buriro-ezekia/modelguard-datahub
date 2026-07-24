#!/usr/bin/env python3
"""Run the complete deterministic ModelGuard showcase in one command."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _run(arguments: list[str], *, expected: set[int] = {0}) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "modelguard", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in expected:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(arguments)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return {
        "command": ["{python}", "-m", "modelguard", *arguments],
        "return_code": completed.returncode,
        "duration_seconds": round(time.monotonic() - started, 4),
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/showcase"))
    parser.add_argument("--keep-state", action="store_true")
    args = parser.parse_args()

    artifacts = (ROOT / args.artifacts_dir).resolve()
    if ROOT not in artifacts.parents:
        raise SystemExit("artifacts directory must be inside the repository")
    if artifacts.exists() and not args.keep_state:
        shutil.rmtree(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)

    paths = {
        "evaluation": artifacts / "evaluation.json",
        "context": artifacts / "context_snapshot.json",
        "diagnosis": artifacts / "diagnosis_report.json",
        "root_markdown": artifacts / "root_cause_report.md",
        "repair_plan": artifacts / "repair_plan.json",
        "validation": artifacts / "repair_validation.json",
        "patch": artifacts / "validated_patch.diff",
        "repair_markdown": artifacts / "validated_repair_report.md",
        "github_state": artifacts / "github_state.json",
        "datahub_state": artifacts / "datahub_state.json",
        "publication": artifacts / "publication_receipt.json",
        "publication_repeat": artifacts / "publication_repeat.json",
        "publication_markdown": artifacts / "publication_report.md",
        "comment": artifacts / "github_pr_comment.md",
    }

    started = time.monotonic()
    commands: list[dict[str, Any]] = []
    commands.append(
        _run(
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
                str(paths["evaluation"]),
            ],
            expected={1},
        )
    )
    commands.append(
        _run(
            [
                "context",
                "collect",
                "--provider",
                "fixture",
                "--lineage-direction",
                "both",
                "--output",
                str(paths["context"]),
            ]
        )
    )
    commands.append(
        _run(
            [
                "diagnose",
                "--evaluation",
                str(paths["evaluation"]),
                "--context",
                str(paths["context"]),
                "--changes",
                "examples/regression_case.json",
                "--output",
                str(paths["diagnosis"]),
                "--markdown-output",
                str(paths["root_markdown"]),
            ]
        )
    )
    commands.append(
        _run(
            [
                "repair",
                "--diagnosis",
                str(paths["diagnosis"]),
                "--evaluation",
                str(paths["evaluation"]),
                "--case",
                "examples/repair_case.json",
                "--workspace",
                "demo/broken_change",
                "--plan-output",
                str(paths["repair_plan"]),
                "--validation-output",
                str(paths["validation"]),
                "--patch-output",
                str(paths["patch"]),
                "--markdown-output",
                str(paths["repair_markdown"]),
            ]
        )
    )

    publish_args = [
        "publish",
        "--diagnosis",
        str(paths["diagnosis"]),
        "--repair-plan",
        str(paths["repair_plan"]),
        "--validation",
        str(paths["validation"]),
        "--patch",
        str(paths["patch"]),
        "--github-mode",
        "fixture",
        "--datahub-mode",
        "fixture",
        "--github-state",
        str(paths["github_state"]),
        "--datahub-state",
        str(paths["datahub_state"]),
        "--apply",
        "--output",
        str(paths["publication"]),
        "--markdown-output",
        str(paths["publication_markdown"]),
        "--comment-output",
        str(paths["comment"]),
    ]
    commands.append(_run(publish_args))
    repeat_args = publish_args.copy()
    repeat_args[repeat_args.index(str(paths["publication"]))] = str(
        paths["publication_repeat"]
    )
    commands.append(_run(repeat_args))

    evaluation = _read(paths["evaluation"])
    context = _read(paths["context"])
    diagnosis = _read(paths["diagnosis"])
    validation = _read(paths["validation"])
    publication = _read(paths["publication"])
    publication_repeat = _read(paths["publication_repeat"])

    channels = {item["channel"]: item for item in publication["channels"]}
    repeated = {item["channel"]: item for item in publication_repeat["channels"]}
    summary = {
        "status": "complete",
        "duration_seconds": round(time.monotonic() - started, 4),
        "metric": evaluation["metric"],
        "f1_before": evaluation["candidate"],
        "f1_after": validation["post_repair_evaluation"]["candidate"],
        "invalid_values_after": validation["post_repair_evaluation"]["invalid_values"],
        "context_provider": context["provider"],
        "upstream_assets": len(context["upstream"]),
        "downstream_assets": len(context["downstream"]),
        "top_hypothesis": diagnosis["hypotheses"][0]["category"],
        "top_score": diagnosis["hypotheses"][0]["score"],
        "repair_status": validation["status"],
        "patch_guard": validation["patch_guard"]["approved"],
        "source_unchanged": validation["source_workspace_unchanged"],
        "delivery_id": publication["delivery_id"],
        "first_publication": {
            "github": channels["github"]["action"],
            "datahub": channels["datahub"]["action"],
        },
        "repeat_publication": {
            "github": repeated["github"]["action"],
            "datahub": repeated["datahub"]["action"],
        },
        "commands": commands,
    }
    summary_path = artifacts / "showcase_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nModelGuard showcase complete")
    print("=" * 30)
    print(f"F1: {summary['f1_before']} -> {summary['f1_after']}")
    print(f"Diagnosis: {summary['top_hypothesis']} ({summary['top_score']})")
    print(f"Repair: {summary['repair_status']} | guard={summary['patch_guard']}")
    print(
        f"Publish: GitHub={channels['github']['action']} "
        f"DataHub={channels['datahub']['action']}"
    )
    print(
        f"Repeat: GitHub={repeated['github']['action']} "
        f"DataHub={repeated['datahub']['action']}"
    )
    print(f"Summary: {summary_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
