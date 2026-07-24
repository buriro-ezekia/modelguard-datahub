"""Command-line interface for ModelGuard."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from modelguard.metrics import MetricEvaluation, MetricPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelguard",
        description="Evaluate candidate model metrics against approved baselines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Evaluate one metric and emit a structured result.",
    )
    evaluate.add_argument("--metric", required=True, help="Metric name, for example f1_score.")
    evaluate.add_argument("--baseline", required=True, type=float)
    evaluate.add_argument("--candidate", required=True, type=float)
    evaluate.add_argument(
        "--max-regression",
        required=True,
        type=float,
        help="Maximum tolerated adverse change before the gate fails.",
    )
    evaluate.add_argument(
        "--direction",
        choices=("higher_is_better", "lower_is_better"),
        default="higher_is_better",
    )
    evaluate.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON evaluation artefact.",
    )

    return parser


def run_evaluate(args: argparse.Namespace) -> int:
    policy = MetricPolicy(
        metric=args.metric,
        maximum_allowed_regression=args.max_regression,
        direction=args.direction,
    )
    evaluation = MetricEvaluation(
        policy=policy,
        baseline=args.baseline,
        candidate=args.candidate,
    )
    payload = evaluation.to_dict()
    rendered = json.dumps(payload, indent=2, sort_keys=True)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")

    print(rendered)
    return 1 if evaluation.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        return run_evaluate(args)

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
