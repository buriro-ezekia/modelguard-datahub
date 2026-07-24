"""Safe publication orchestration for validated ModelGuard repairs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from modelguard.reporting.datahub_writer import DataHubIncidentWriter
from modelguard.reporting.github_comment import GitHubCommentWriter

ChannelMode = Literal["off", "fixture", "live"]
PublicationStatus = Literal["dry_run", "published", "partial", "failed"]


class PublicationError(RuntimeError):
    """Raised when publication inputs are unsafe or inconsistent."""


@dataclass(frozen=True, slots=True)
class ChannelReceipt:
    """Outcome for one publication channel."""

    channel: str
    mode: ChannelMode
    status: str
    action: str
    external_id: str | None = None
    url: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublicationPlan:
    """Immutable payload prepared before any external write."""

    delivery_id: str
    repository: str
    pull_request: int
    github_comment: str
    datahub_asset_urn: str
    datahub_incident_title: str
    datahub_incident_description: str
    datahub_resolution_message: str
    marker: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    """Auditable result of dry-run or applied publication."""

    delivery_id: str
    status: PublicationStatus
    applied: bool
    plan: PublicationPlan
    channels: tuple[ChannelReceipt, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["plan"] = self.plan.to_dict()
        value["channels"] = [item.to_dict() for item in self.channels]
        return value


@dataclass(frozen=True, slots=True)
class PublicationInputs:
    """Validated artefacts required for publishing."""

    diagnosis: dict[str, Any]
    repair_plan: dict[str, Any]
    validation: dict[str, Any]
    patch: str
    repository: str
    pull_request: int
    datahub_asset_urn: str | None = None

    def validate(self) -> None:
        if self.diagnosis.get("status") != "ranked":
            raise PublicationError("publication requires a ranked diagnosis")
        hypotheses = self.diagnosis.get("hypotheses")
        if not isinstance(hypotheses, list) or not hypotheses:
            raise PublicationError("diagnosis must contain ranked hypotheses")
        top = hypotheses[0]
        if top.get("confidence") != "high" or float(top.get("score", 0.0)) < 0.8:
            raise PublicationError("publication requires a high-confidence leading diagnosis")
        if self.validation.get("status") != "validated":
            raise PublicationError("publication requires a validated repair")
        guard = self.validation.get("patch_guard")
        if not isinstance(guard, dict) or guard.get("approved") is not True:
            raise PublicationError("publication requires an approved patch guard")
        if self.validation.get("metric_restored") is not True:
            raise PublicationError("publication requires a restored metric")
        if self.validation.get("source_workspace_unchanged") is not True:
            raise PublicationError("publication requires an unchanged source workspace")
        if self.repair_plan.get("repair_id") != self.validation.get("repair_id"):
            raise PublicationError("repair plan and validation repair IDs do not match")
        if not self.patch.strip():
            raise PublicationError("validated patch must not be empty")
        if "/" not in self.repository or self.repository.startswith("/"):
            raise PublicationError("repository must use owner/name form")
        if self.pull_request < 1:
            raise PublicationError("pull request must be positive")
        asset = self.resolved_asset_urn
        if not asset.startswith("urn:li:dataset:"):
            raise PublicationError(
                "DataHub incident publication currently requires a dataset URN"
            )

    @property
    def top_hypothesis(self) -> dict[str, Any]:
        return self.diagnosis["hypotheses"][0]

    @property
    def resolved_asset_urn(self) -> str:
        explicit = (self.datahub_asset_urn or "").strip()
        if explicit:
            return explicit
        affected = str(self.top_hypothesis.get("affected_asset") or "").strip()
        if affected:
            return affected
        return str(self.diagnosis.get("source_urn") or "").strip()


class PublicationCoordinator:
    """Build an immutable plan and publish through configured channel writers."""

    def __init__(
        self,
        *,
        github_writer: GitHubCommentWriter,
        datahub_writer: DataHubIncidentWriter,
    ) -> None:
        self.github_writer = github_writer
        self.datahub_writer = datahub_writer

    def publish(self, inputs: PublicationInputs, *, apply: bool) -> PublicationReceipt:
        inputs.validate()
        plan = build_publication_plan(inputs)
        github = self.github_writer.publish(plan, apply=apply)
        datahub = self.datahub_writer.publish(plan, apply=apply)
        channels = (github, datahub)
        statuses = {channel.status for channel in channels if channel.mode != "off"}
        if not apply:
            status: PublicationStatus = "dry_run"
        elif statuses and statuses <= {"published", "noop"}:
            status = "published"
        elif "failed" in statuses and statuses - {"failed"}:
            status = "partial"
        elif "failed" in statuses:
            status = "failed"
        else:
            status = "published"
        warnings = tuple(
            detail
            for channel in channels
            for detail in channel.details.get("warnings", [])
            if isinstance(detail, str)
        )
        return PublicationReceipt(
            delivery_id=plan.delivery_id,
            status=status,
            applied=apply,
            plan=plan,
            channels=channels,
            warnings=warnings,
        )


def build_publication_plan(inputs: PublicationInputs) -> PublicationPlan:
    """Create stable, channel-neutral publication payloads."""

    top = inputs.top_hypothesis
    validation = inputs.validation
    before = validation["pre_repair_evaluation"]
    after = validation["post_repair_evaluation"]
    repair_id = str(inputs.repair_plan["repair_id"])
    validation_id = str(validation["validation_id"])
    canonical = json.dumps(
        {
            "diagnosis_id": inputs.diagnosis.get("diagnosis_id"),
            "repair_id": repair_id,
            "validation_id": validation_id,
            "repository": inputs.repository,
            "pull_request": inputs.pull_request,
            "patch_sha256": hashlib.sha256(inputs.patch.encode()).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    delivery_id = f"delivery-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
    marker = f"<!-- modelguard:delivery:{delivery_id} -->"
    repository_url = f"https://github.com/{inputs.repository}"
    pr_url = f"{repository_url}/pull/{inputs.pull_request}"
    fields = ", ".join(f"`{item}`" for item in top.get("affected_fields", [])) or "none"
    comment = _github_comment(
        marker=marker,
        delivery_id=delivery_id,
        diagnosis=inputs.diagnosis,
        repair_plan=inputs.repair_plan,
        validation=validation,
        patch=inputs.patch,
        pr_url=pr_url,
        affected_fields=fields,
    )
    title = f"ModelGuard repaired {before['metric']} regression"
    description = "\n".join(
        (
            f"[modelguard-delivery:{delivery_id}]",
            f"Pull request: {pr_url}",
            f"Diagnosis: {top.get('title')}",
            f"Confidence: {top.get('confidence')} ({float(top.get('score', 0.0)):.4f})",
            f"Before repair: {before.get('candidate')}",
            f"After repair: {after.get('candidate')}",
            f"Validation: {validation_id}",
            f"Repair: {repair_id}",
        )
    )
    resolution = (
        f"Validated repair {repair_id} restored {before['metric']} from "
        f"{before.get('candidate')} to {after.get('candidate')}; "
        f"validation {validation_id}. Source workspace unchanged."
    )
    return PublicationPlan(
        delivery_id=delivery_id,
        repository=inputs.repository,
        pull_request=inputs.pull_request,
        github_comment=comment,
        datahub_asset_urn=inputs.resolved_asset_urn,
        datahub_incident_title=title,
        datahub_incident_description=description,
        datahub_resolution_message=resolution,
        marker=marker,
    )


def render_publication_markdown(receipt: PublicationReceipt) -> str:
    """Render publication actions and receipts for human review."""

    lines = [
        "# ModelGuard Publication Report",
        "",
        f"- **Delivery:** `{receipt.delivery_id}`",
        f"- **Status:** `{receipt.status}`",
        f"- **Applied:** `{str(receipt.applied).lower()}`",
        f"- **Pull request:** `{receipt.plan.repository}#{receipt.plan.pull_request}`",
        f"- **DataHub asset:** `{receipt.plan.datahub_asset_urn}`",
        "",
        "## Channel receipts",
        "",
        "| Channel | Mode | Status | Action | External ID |",
        "|---|---|---|---|---|",
    ]
    for item in receipt.channels:
        lines.append(
            f"| {item.channel} | {item.mode} | {item.status} | {item.action} | "
            f"{item.external_id or '—'} |"
        )
    lines.extend(
        (
            "",
            "## Safety statement",
            "",
            "Publication requires a validated repair, an approved patch guard, a restored "
            "metric and proof that the source workspace was unchanged. External writes are "
            "disabled unless `--apply` is supplied.",
            "",
        )
    )
    return "\n".join(lines)


def write_publication_outputs(
    receipt: PublicationReceipt,
    *,
    output: Path,
    markdown_output: Path | None,
    comment_output: Path | None,
) -> None:
    """Persist publication evidence artefacts."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_publication_markdown(receipt), encoding="utf-8")
    if comment_output is not None:
        comment_output.parent.mkdir(parents=True, exist_ok=True)
        comment_output.write_text(receipt.plan.github_comment, encoding="utf-8")


def _github_comment(
    *,
    marker: str,
    delivery_id: str,
    diagnosis: dict[str, Any],
    repair_plan: dict[str, Any],
    validation: dict[str, Any],
    patch: str,
    pr_url: str,
    affected_fields: str,
) -> str:
    top = diagnosis["hypotheses"][0]
    before = validation["pre_repair_evaluation"]
    after = validation["post_repair_evaluation"]
    commands = validation.get("commands", [])
    passed_commands = sum(1 for item in commands if item.get("return_code") == 0)
    return "\n".join(
        (
            marker,
            "## ✅ ModelGuard validated repair",
            "",
            f"**Delivery:** `{delivery_id}`  ",
            f"**Root cause:** {top.get('title')}  ",
            f"**Confidence:** `{top.get('confidence')}` (`{float(top.get('score', 0.0)):.4f}`)  ",
            f"**Affected asset:** `{top.get('affected_asset')}`  ",
            f"**Affected fields:** {affected_fields}",
            "",
            "| Check | Result |",
            "|---|---:|",
            f"| `{before.get('metric')}` before repair | `{before.get('candidate')}` |",
            f"| `{before.get('metric')}` after repair | `{after.get('candidate')}` |",
            f"| Invalid values after repair | `{after.get('invalid_values', 'n/a')}` |",
            f"| Validation commands passed | `{passed_commands}/{len(commands)}` |",
            f"| Source workspace unchanged | `{validation.get('source_workspace_unchanged')}` |",
            "",
            f"**Repair strategy:** `{repair_plan.get('strategy')}`  ",
            f"**Repair ID:** `{repair_plan.get('repair_id')}`  ",
            f"**Validation ID:** `{validation.get('validation_id')}`",
            "",
            "<details>",
            "<summary>Validated patch</summary>",
            "",
            "```diff",
            patch.rstrip(),
            "```",
            "",
            "</details>",
            "",
            f"Review this validated patch in {pr_url}. ModelGuard did not apply or merge it.",
            "",
        )
    )
