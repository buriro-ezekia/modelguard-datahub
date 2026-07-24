"""Constrained repair generation for supported high-confidence diagnoses."""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

RepairPlanStatus = Literal["proposed"]


class RepairGenerationError(RuntimeError):
    """Raised when ModelGuard cannot safely construct a supported repair."""


@dataclass(frozen=True, slots=True)
class RepairCase:
    """Explicit repair and validation boundary supplied by the repository."""

    strategy: str
    target_file: str
    target_symbol: str
    denominator: str
    fallback: str
    allowed_paths: tuple[str, ...]
    validation_commands: tuple[tuple[str, ...], ...]
    metric_output: str
    timeout_seconds: int = 60

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepairCase:
        validation = value.get("validation") or {}
        commands = validation.get("commands") or []
        return cls(
            strategy=str(value.get("strategy") or ""),
            target_file=str(value.get("target_file") or ""),
            target_symbol=str(value.get("target_symbol") or ""),
            denominator=str(value.get("denominator") or ""),
            fallback=str(value.get("fallback") or "0.0"),
            allowed_paths=tuple(str(item) for item in value.get("allowed_paths", [])),
            validation_commands=tuple(
                tuple(str(part) for part in command)
                for command in commands
                if isinstance(command, list)
            ),
            metric_output=str(validation.get("metric_output") or ""),
            timeout_seconds=int(validation.get("timeout_seconds") or 60),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FilePatch:
    """One reviewable in-memory file replacement."""

    path: str
    original_sha256: str
    patched_sha256: str
    original_content: str
    patched_content: str
    diff: str
    added_lines: int
    removed_lines: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FilePatch:
        return cls(
            path=str(value["path"]),
            original_sha256=str(value["original_sha256"]),
            patched_sha256=str(value["patched_sha256"]),
            original_content=str(value["original_content"]),
            patched_content=str(value["patched_content"]),
            diff=str(value["diff"]),
            added_lines=int(value["added_lines"]),
            removed_lines=int(value["removed_lines"]),
        )


@dataclass(frozen=True, slots=True)
class RepairPlan:
    """A generated patch proposal that has not yet been authorised or applied."""

    repair_id: str
    diagnosis_id: str
    hypothesis_id: str
    category: str
    confidence: str
    score: float
    status: RepairPlanStatus
    strategy: str
    patches: tuple[FilePatch, ...]
    rationale: str
    safety_notes: tuple[str, ...]

    @property
    def combined_diff(self) -> str:
        return "\n".join(patch.diff.rstrip() for patch in self.patches) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepairPlan:
        return cls(
            repair_id=str(value["repair_id"]),
            diagnosis_id=str(value["diagnosis_id"]),
            hypothesis_id=str(value["hypothesis_id"]),
            category=str(value["category"]),
            confidence=str(value["confidence"]),
            score=float(value["score"]),
            status="proposed",
            strategy=str(value["strategy"]),
            patches=tuple(FilePatch.from_dict(item) for item in value.get("patches", [])),
            rationale=str(value.get("rationale") or ""),
            safety_notes=tuple(str(item) for item in value.get("safety_notes", [])),
        )


class ConstrainedRepairGenerator:
    """Generate the smallest supported source repair from auditable evidence."""

    supported_strategy = "guarded_division"

    def generate(
        self,
        *,
        diagnosis: dict[str, Any],
        case: RepairCase,
        workspace: Path,
    ) -> RepairPlan:
        hypothesis = self._leading_hypothesis(diagnosis)
        self._validate_case(diagnosis, hypothesis, case)
        target = self._safe_target(workspace, case.target_file)
        try:
            original = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise RepairGenerationError(
                f"cannot read target file {case.target_file}: {exc}"
            ) from exc

        patched = self._insert_guard(original, case)
        try:
            compile(patched, case.target_file, "exec")
        except SyntaxError as exc:
            raise RepairGenerationError(f"generated source is not valid Python: {exc}") from exc

        diff_lines = difflib.unified_diff(
            original.splitlines(),
            patched.splitlines(),
            fromfile=f"a/{case.target_file}",
            tofile=f"b/{case.target_file}",
            lineterm="",
        )
        diff = "\n".join(diff_lines) + "\n"
        file_patch = FilePatch(
            path=case.target_file,
            original_sha256=_sha256(original),
            patched_sha256=_sha256(patched),
            original_content=original,
            patched_content=patched,
            diff=diff,
            added_lines=_count_diff_lines(diff, "+"),
            removed_lines=_count_diff_lines(diff, "-"),
        )
        repair_id = _stable_id(
            diagnosis["diagnosis_id"],
            hypothesis["hypothesis_id"],
            case.to_dict(),
            file_patch.original_sha256,
            file_patch.patched_sha256,
        )
        return RepairPlan(
            repair_id=repair_id,
            diagnosis_id=str(diagnosis["diagnosis_id"]),
            hypothesis_id=str(hypothesis["hypothesis_id"]),
            category=str(hypothesis["category"]),
            confidence=str(hypothesis["confidence"]),
            score=float(hypothesis["score"]),
            status="proposed",
            strategy=case.strategy,
            patches=(file_patch,),
            rationale=(
                "Insert an explicit non-positive denominator guard before the diagnosed "
                "division while preserving all other source lines."
            ),
            safety_notes=(
                "The source workspace is not modified during generation.",
                "The proposal changes one Python file and one function only.",
                "Validation must run in an isolated copy before the patch is considered usable.",
            ),
        )

    @staticmethod
    def _leading_hypothesis(diagnosis: dict[str, Any]) -> dict[str, Any]:
        if diagnosis.get("status") != "ranked":
            raise RepairGenerationError("repair generation requires a ranked diagnosis")
        top_id = diagnosis.get("top_hypothesis_id")
        hypotheses = diagnosis.get("hypotheses") or []
        for hypothesis in hypotheses:
            if isinstance(hypothesis, dict) and hypothesis.get("hypothesis_id") == top_id:
                return hypothesis
        raise RepairGenerationError("top hypothesis is missing from the diagnosis report")

    @staticmethod
    def _validate_case(
        diagnosis: dict[str, Any],
        hypothesis: dict[str, Any],
        case: RepairCase,
    ) -> None:
        if case.strategy != ConstrainedRepairGenerator.supported_strategy:
            raise RepairGenerationError(f"unsupported repair strategy: {case.strategy}")
        if hypothesis.get("category") != "feature_transformation":
            raise RepairGenerationError("only feature_transformation diagnoses are supported")
        if hypothesis.get("confidence") != "high" or float(hypothesis.get("score", 0.0)) < 0.8:
            raise RepairGenerationError(
                "repair generation requires high confidence and score >= 0.8"
            )
        affected = {str(item) for item in hypothesis.get("affected_fields", [])}
        if case.denominator not in affected:
            raise RepairGenerationError("denominator is not cited by the leading diagnosis")
        change_paths = {
            str(item.get("attributes", {}).get("path"))
            for item in diagnosis.get("evidence", [])
            if isinstance(item, dict) and item.get("kind") == "change"
        }
        if case.target_file not in change_paths:
            raise RepairGenerationError("target file is not supported by changed-file evidence")
        if not case.target_symbol or not case.denominator:
            raise RepairGenerationError("target_symbol and denominator are required")
        if not case.validation_commands or not case.metric_output:
            raise RepairGenerationError("validation commands and metric output are required")

    @staticmethod
    def _safe_target(workspace: Path, target_file: str) -> Path:
        relative = PurePosixPath(target_file)
        if relative.is_absolute() or ".." in relative.parts:
            raise RepairGenerationError("target file must be a safe relative path")
        root = workspace.resolve()
        target = (root / Path(*relative.parts)).resolve()
        if root not in target.parents:
            raise RepairGenerationError("target file escapes the workspace")
        return target

    @staticmethod
    def _insert_guard(source: str, case: RepairCase) -> str:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise RepairGenerationError(f"target source is not valid Python: {exc}") from exc
        matches: list[ast.Return] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != case.target_symbol:
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Return) or not isinstance(child.value, ast.BinOp):
                    continue
                if not isinstance(child.value.op, ast.Div):
                    continue
                denominator_names = {
                    item.id for item in ast.walk(child.value.right) if isinstance(item, ast.Name)
                }
                if case.denominator in denominator_names:
                    matches.append(child)
        if len(matches) != 1:
            raise RepairGenerationError(
                "expected exactly one matching division return in the target symbol"
            )
        match = matches[0]
        lines = source.splitlines(keepends=True)
        return_line = lines[match.lineno - 1]
        indentation = return_line[: len(return_line) - len(return_line.lstrip())]
        guard = [
            f"{indentation}if {case.denominator} <= 0:\n",
            f"{indentation}    return {case.fallback}\n",
        ]
        return "".join((*lines[: match.lineno - 1], *guard, *lines[match.lineno - 1 :]))


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _stable_id(*values: Any) -> str:
    rendered = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return f"repair-{hashlib.sha256(rendered.encode('utf-8')).hexdigest()[:12]}"


def _count_diff_lines(diff: str, prefix: str) -> int:
    return sum(
        1
        for line in diff.splitlines()
        if line.startswith(prefix) and not line.startswith(f"{prefix}{prefix}{prefix}")
    )
