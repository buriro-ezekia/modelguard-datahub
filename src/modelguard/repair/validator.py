"""Isolated execution and independent validation of generated repair plans."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from modelguard.metrics import MetricEvaluation, MetricPolicy
from modelguard.repair.generator import RepairCase, RepairPlan
from modelguard.repair.patch_guard import (
    PatchGuardDecision,
    PatchGuardPolicy,
    evaluate_patch_guard,
)

ValidationStatus = Literal["validated", "failed", "rejected"]


class RepairValidationError(RuntimeError):
    """Raised when validation inputs are malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result of one isolated validation command."""

    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.return_code == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RepairValidationReport:
    """Auditable result of isolated patch validation."""

    validation_id: str
    repair_id: str
    status: ValidationStatus
    isolated_workspace: bool
    source_workspace_unchanged: bool
    patch_guard: PatchGuardDecision
    changed_files: tuple[str, ...]
    commands: tuple[CommandResult, ...]
    pre_repair_evaluation: dict[str, Any]
    post_repair_evaluation: dict[str, Any] | None
    metric_restored: bool
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["patch_guard"] = self.patch_guard.to_dict()
        value["commands"] = [command.to_dict() for command in self.commands]
        return value


class RepairValidator:
    """Apply a proposed patch only to a temporary copy and validate it independently."""

    def __init__(self, guard_policy: PatchGuardPolicy | None = None) -> None:
        self.guard_policy = guard_policy or PatchGuardPolicy()

    def validate(
        self,
        *,
        plan: RepairPlan,
        case: RepairCase,
        evaluation: dict[str, Any],
        workspace: Path,
    ) -> RepairValidationReport:
        guard = evaluate_patch_guard(plan, case, self.guard_policy)
        source_hashes = self._source_hashes(plan, workspace)
        if not guard.approved:
            return self._report(
                plan=plan,
                status="rejected",
                guard=guard,
                source_unchanged=self._source_unchanged(source_hashes, workspace),
                commands=(),
                evaluation=evaluation,
                post=None,
                metric_restored=False,
                warnings=("Static patch guard rejected the proposal before execution.",),
            )

        commands: list[CommandResult] = []
        post_evaluation: dict[str, Any] | None = None
        metric_restored = False
        status: ValidationStatus = "failed"
        warnings: list[str] = []

        with tempfile.TemporaryDirectory(prefix="modelguard-repair-") as temp_directory:
            isolated = Path(temp_directory) / "workspace"
            self._copy_workspace(workspace, isolated)
            self._apply_plan(plan, isolated)
            for patch in plan.patches:
                if patch.path.endswith(".py"):
                    commands.append(
                        self._run_command(
                            (sys.executable, "-m", "py_compile", patch.path),
                            isolated,
                            case.timeout_seconds,
                        )
                    )
            if all(command.passed for command in commands):
                for configured in case.validation_commands:
                    result = self._run_command(
                        self._resolve_command(configured),
                        isolated,
                        case.timeout_seconds,
                    )
                    commands.append(result)
                    if not result.passed:
                        break
            if all(command.passed for command in commands):
                post_evaluation = self._read_metric_output(isolated / case.metric_output)
                metric_result = self._metric_gate(evaluation, post_evaluation)
                post_evaluation = {
                    **post_evaluation,
                    "gate": metric_result.to_dict(),
                }
                metric_restored = not metric_result.failed
                status = "validated" if metric_restored else "failed"
                if not metric_restored:
                    warnings.append("Post-repair metric remains outside the configured tolerance.")
            else:
                warnings.append("At least one isolated validation command failed.")

        source_unchanged = self._source_unchanged(source_hashes, workspace)
        if not source_unchanged:
            status = "failed"
            warnings.append("Source workspace changed during validation; the result is invalid.")
        return self._report(
            plan=plan,
            status=status,
            guard=guard,
            source_unchanged=source_unchanged,
            commands=tuple(commands),
            evaluation=evaluation,
            post=post_evaluation,
            metric_restored=metric_restored,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _copy_workspace(source: Path, destination: Path) -> None:
        try:
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".venv",
                    "__pycache__",
                    ".pytest_cache",
                    "artifacts",
                ),
            )
        except OSError as exc:
            raise RepairValidationError(f"cannot create isolated workspace: {exc}") from exc

    @staticmethod
    def _apply_plan(plan: RepairPlan, workspace: Path) -> None:
        for patch in plan.patches:
            target = (workspace / patch.path).resolve()
            if workspace.resolve() not in target.parents:
                raise RepairValidationError(f"patch path escapes isolated workspace: {patch.path}")
            try:
                existing = target.read_text(encoding="utf-8")
            except OSError as exc:
                raise RepairValidationError(
                    f"cannot read isolated target {patch.path}: {exc}"
                ) from exc
            if _sha256(existing) != patch.original_sha256:
                raise RepairValidationError(f"source hash mismatch for {patch.path}")
            target.write_text(patch.patched_content, encoding="utf-8")

    @staticmethod
    def _resolve_command(command: tuple[str, ...]) -> tuple[str, ...]:
        if not command:
            raise RepairValidationError("validation command must not be empty")
        resolved = (sys.executable if command[0] == "{python}" else command[0], *command[1:])
        allowed = {sys.executable, "python", "python3"}
        if resolved[0] not in allowed:
            raise RepairValidationError(f"validation executable is not allowed: {resolved[0]}")
        return tuple(resolved)

    @staticmethod
    def _run_command(command: tuple[str, ...], workspace: Path, timeout: int) -> CommandResult:
        started = time.monotonic()
        environment = os.environ.copy()
        python_path = os.pathsep.join(
            filter(
                None,
                (str(workspace / "src"), str(workspace), environment.get("PYTHONPATH")),
            )
        )
        environment["PYTHONPATH"] = python_path
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
            return CommandResult(
                command=command,
                return_code=completed.returncode,
                stdout=completed.stdout[-12000:],
                stderr=completed.stderr[-12000:],
                duration_seconds=round(time.monotonic() - started, 4),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                return_code=124,
                stdout=_timeout_text(exc.stdout),
                stderr=_timeout_text(exc.stderr),
                duration_seconds=round(time.monotonic() - started, 4),
                timed_out=True,
            )

    @staticmethod
    def _read_metric_output(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RepairValidationError(f"cannot read post-repair metric output: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RepairValidationError(f"invalid post-repair metric JSON: {exc}") from exc
        if not isinstance(value, dict) or "candidate" not in value:
            raise RepairValidationError("post-repair metric output must contain candidate")
        return value

    @staticmethod
    def _metric_gate(
        evaluation: dict[str, Any],
        post_evaluation: dict[str, Any],
    ) -> MetricEvaluation:
        metric = str(evaluation.get("metric") or "")
        if post_evaluation.get("metric") not in {None, metric}:
            raise RepairValidationError("post-repair metric name does not match Phase 1")
        policy = MetricPolicy(
            metric=metric,
            maximum_allowed_regression=float(evaluation["maximum_allowed_regression"]),
            direction=str(evaluation.get("direction") or "higher_is_better"),
        )
        return MetricEvaluation(
            policy=policy,
            baseline=float(evaluation["baseline"]),
            candidate=float(post_evaluation["candidate"]),
        )

    @staticmethod
    def _source_hashes(plan: RepairPlan, workspace: Path) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for patch in plan.patches:
            path = workspace / patch.path
            try:
                hashes[patch.path] = _sha256(path.read_text(encoding="utf-8"))
            except OSError as exc:
                raise RepairValidationError(f"cannot hash source file {patch.path}: {exc}") from exc
        return hashes

    @staticmethod
    def _source_unchanged(hashes: dict[str, str], workspace: Path) -> bool:
        for relative, expected in hashes.items():
            try:
                current = _sha256((workspace / relative).read_text(encoding="utf-8"))
            except OSError:
                return False
            if current != expected:
                return False
        return True

    @staticmethod
    def _report(
        *,
        plan: RepairPlan,
        status: ValidationStatus,
        guard: PatchGuardDecision,
        source_unchanged: bool,
        commands: tuple[CommandResult, ...],
        evaluation: dict[str, Any],
        post: dict[str, Any] | None,
        metric_restored: bool,
        warnings: tuple[str, ...],
    ) -> RepairValidationReport:
        rendered = json.dumps(
            (plan.repair_id, status, post, [command.return_code for command in commands]),
            sort_keys=True,
            default=str,
        )
        validation_id = f"validation-{hashlib.sha256(rendered.encode()).hexdigest()[:12]}"
        return RepairValidationReport(
            validation_id=validation_id,
            repair_id=plan.repair_id,
            status=status,
            isolated_workspace=True,
            source_workspace_unchanged=source_unchanged,
            patch_guard=guard,
            changed_files=tuple(patch.path for patch in plan.patches),
            commands=commands,
            pre_repair_evaluation=dict(evaluation),
            post_repair_evaluation=post,
            metric_restored=metric_restored,
            warnings=warnings,
        )


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _timeout_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
