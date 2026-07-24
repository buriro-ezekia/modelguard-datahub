"""Command-line interface for ModelGuard."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from modelguard.config import ConfigurationError, load_config
from modelguard.context import DataHubContextError, build_context_provider
from modelguard.diagnosis import ChangeSet, DiagnosisAgent, DiagnosisError
from modelguard.diagnosis.ranking import RankingPolicy
from modelguard.metrics import MetricEvaluation, MetricPolicy
from modelguard.models import ContextSnapshot
from modelguard.orchestrator import ContextCollector
from modelguard.repair import (
    ConstrainedRepairGenerator,
    RepairCase,
    RepairGenerationError,
    RepairValidationError,
    RepairValidator,
)
from modelguard.reporting import (
    DataHubIncidentWriter,
    GitHubCommentWriter,
    PublicationCoordinator,
    PublicationError,
    PublicationInputs,
    render_diagnosis_markdown,
    render_repair_markdown,
    write_publication_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelguard",
        description=(
            "Detect ML regressions, collect DataHub evidence, rank root causes, "
            "validate constrained repairs and publish verified outcomes."
        ),
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
    context_subparsers = context.add_subparsers(dest="context_command", required=True)

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

    diagnose = subparsers.add_parser(
        "diagnose",
        help="Generate and rank evidence-backed root-cause hypotheses.",
    )
    diagnose.add_argument("--evaluation", type=Path, required=True)
    diagnose.add_argument("--context", type=Path, required=True)
    diagnose.add_argument("--changes", type=Path, required=True)
    diagnose.add_argument("--output", type=Path, required=True)
    diagnose.add_argument("--markdown-output", type=Path)
    diagnose.add_argument("--min-confidence", type=float, default=0.45)
    diagnose.add_argument("--min-margin", type=float, default=0.08)

    repair = subparsers.add_parser(
        "repair",
        help="Generate and independently validate a constrained repair.",
    )
    repair.add_argument("--diagnosis", type=Path, required=True)
    repair.add_argument("--evaluation", type=Path, required=True)
    repair.add_argument("--case", type=Path, required=True)
    repair.add_argument("--workspace", type=Path, required=True)
    repair.add_argument("--plan-output", type=Path, required=True)
    repair.add_argument("--validation-output", type=Path, required=True)
    repair.add_argument("--patch-output", type=Path, required=True)
    repair.add_argument("--markdown-output", type=Path)

    publish = subparsers.add_parser(
        "publish",
        help="Publish a validated repair to GitHub and DataHub.",
    )
    publish.add_argument("--diagnosis", type=Path, required=True)
    publish.add_argument("--repair-plan", type=Path, required=True)
    publish.add_argument("--validation", type=Path, required=True)
    publish.add_argument("--patch", type=Path, required=True)
    publish.add_argument("--repository")
    publish.add_argument("--pull-request", type=int)
    publish.add_argument("--datahub-asset-urn")
    publish.add_argument(
        "--github-mode",
        choices=("off", "fixture", "live"),
        default="fixture",
    )
    publish.add_argument(
        "--datahub-mode",
        choices=("off", "fixture", "live"),
        default="fixture",
    )
    publish.add_argument(
        "--github-state",
        type=Path,
        default=Path("artifacts/github_publication_state.json"),
    )
    publish.add_argument(
        "--datahub-state",
        type=Path,
        default=Path("artifacts/datahub_incident_state.json"),
    )
    publish.add_argument("--github-api-url", default="https://api.github.com")
    publish.add_argument("--datahub-graphql-url")
    publish.add_argument("--apply", action="store_true")
    publish.add_argument("--output", type=Path, required=True)
    publish.add_argument("--markdown-output", type=Path)
    publish.add_argument("--comment-output", type=Path)

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


def run_diagnose(args: argparse.Namespace) -> int:
    evaluation = _read_json(args.evaluation)
    context = ContextSnapshot.from_dict(_read_json(args.context))
    changes = ChangeSet.from_dict(_read_json(args.changes))
    agent = DiagnosisAgent(
        policy=RankingPolicy(
            min_confidence=args.min_confidence,
            min_margin=args.min_margin,
        )
    )
    report = agent.diagnose(
        evaluation=evaluation,
        context=context,
        changes=changes,
    )
    _render_json(report.to_dict(), args.output)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            render_diagnosis_markdown(report),
            encoding="utf-8",
        )
    return 0 if report.status == "ranked" else 3


def run_repair(args: argparse.Namespace) -> int:
    diagnosis = _read_json(args.diagnosis)
    evaluation = _read_json(args.evaluation)
    case = RepairCase.from_dict(_read_json(args.case))
    plan = ConstrainedRepairGenerator().generate(
        diagnosis=diagnosis,
        case=case,
        workspace=args.workspace,
    )
    validation = RepairValidator().validate(
        plan=plan,
        case=case,
        evaluation=evaluation,
        workspace=args.workspace,
    )
    _write_json(plan.to_dict(), args.plan_output)
    _write_json(validation.to_dict(), args.validation_output)
    if validation.status == "validated":
        args.patch_output.parent.mkdir(parents=True, exist_ok=True)
        args.patch_output.write_text(plan.combined_diff, encoding="utf-8")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            render_repair_markdown(plan, validation),
            encoding="utf-8",
        )
    print(json.dumps(validation.to_dict(), indent=2, sort_keys=True))
    if validation.status == "validated":
        return 0
    if validation.status == "rejected":
        return 4
    return 5


def run_publish(args: argparse.Namespace) -> int:
    diagnosis = _read_json(args.diagnosis)
    repair_plan = _read_json(args.repair_plan)
    validation = _read_json(args.validation)
    try:
        patch = args.patch.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {args.patch}: {exc}") from exc
    repository = args.repository or diagnosis.get("repository")
    pull_request = args.pull_request or diagnosis.get("pull_request")
    if not isinstance(repository, str):
        raise PublicationError("repository is required for publication")
    if not isinstance(pull_request, int):
        raise PublicationError("pull request is required for publication")
    inputs = PublicationInputs(
        diagnosis=diagnosis,
        repair_plan=repair_plan,
        validation=validation,
        patch=patch,
        repository=repository,
        pull_request=pull_request,
        datahub_asset_urn=args.datahub_asset_urn,
    )
    coordinator = PublicationCoordinator(
        github_writer=GitHubCommentWriter(
            mode=args.github_mode,
            fixture_state=args.github_state,
            api_url=args.github_api_url,
        ),
        datahub_writer=DataHubIncidentWriter(
            mode=args.datahub_mode,
            fixture_state=args.datahub_state,
            graphql_url=args.datahub_graphql_url,
        ),
    )
    receipt = coordinator.publish(inputs, apply=args.apply)
    write_publication_outputs(
        receipt,
        output=args.output,
        markdown_output=args.markdown_output,
        comment_output=args.comment_output,
    )
    print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    return 0 if receipt.status in {"dry_run", "published"} else 6


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _write_json(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_json(payload: dict[str, Any], output: Path | None) -> None:
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
        if args.command == "diagnose":
            return run_diagnose(args)
        if args.command == "repair":
            return run_repair(args)
        if args.command == "publish":
            return run_publish(args)
    except (
        ConfigurationError,
        DataHubContextError,
        DiagnosisError,
        PublicationError,
        RepairGenerationError,
        RepairValidationError,
        ValueError,
    ) as exc:
        print(f"modelguard: {exc}", file=sys.stderr)
        return 2

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
