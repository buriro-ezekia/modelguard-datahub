"""Command-line interface for ModelGuard."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from modelguard.config import ConfigurationError, load_config
from modelguard.context import DataHubContextError, build_context_provider
from modelguard.metrics import MetricEvaluation, MetricPolicy
from modelguard.orchestrator import ContextCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelguard",
        description="Detect ML regressions and collect DataHub evidence for diagnosis.",
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
    evaluate.add_argument("--output", type=Path, help="Optional JSON evaluation path.")

    context = subparsers.add_parser("context", help="Collect or verify DataHub context.")
    context_subparsers = context.add_subparsers(
        dest="context_command", required=True
    )

    context_collect = context_subparsers.add_parser(
        "collect",
        help="Collect entity, schema and lineage context.",
    )
    _add_context_arguments(context_collect)
    context_collect.add_argument("--output", type=Path, required=True)

    context_check = context_subparsers.add_parser(
        "check",
        help="Verify the configured context provider.",
    )
    context_check.add_argument(
        "--config", type=Path, default=Path("config/modelguard.yml")
    )
    context_check.add_argument("--provider", choices=("fixture", "sdk", "mcp"))

    return parser


def _add_context_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("config/modelguard.yml"))
    parser.add_argument("--provider", choices=("fixture", "sdk", "mcp"))
    parser.add_argument(
        "--urn", help="Override the model or dataset URN from configuration."
    )
    parser.add_argument("--column", help="Optional column for column-level lineage.")
    parser.add_argument(
        "--lineage-direction",
        choices=("upstream", "downstream", "both"),
        default="both",
    )


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
    _render_json(evaluation.to_dict(), args.output)
    return 1 if evaluation.failed else 0


def run_context_collect(args: argparse.Namespace) -> int:
    config = load_config(args.config).with_provider(args.provider)
    provider = build_context_provider(config.datahub)
    collector = ContextCollector(config=config, provider=provider)
    snapshot = collector.collect(
        source_urn=args.urn,
        source_column=args.column,
        direction=args.lineage_direction,
    )
    _render_json(snapshot.to_dict(), args.output)
    return 0


def run_context_check(args: argparse.Namespace) -> int:
    config = load_config(args.config).with_provider(args.provider)
    provider = build_context_provider(config.datahub)
    ContextCollector(config=config, provider=provider).check()
    _render_json({"provider": config.datahub.provider, "status": "available"}, None)
    return 0


def _render_json(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            return run_evaluate(args)
        if args.command == "context" and args.context_command == "collect":
            return run_context_collect(args)
        if args.command == "context" and args.context_command == "check":
            return run_context_check(args)
    except (ConfigurationError, DataHubContextError, ValueError) as exc:
        print(f"modelguard: {exc}", file=sys.stderr)
        return 2

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
