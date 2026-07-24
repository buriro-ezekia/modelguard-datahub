"""Static guardrails for generated repair plans."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

from modelguard.repair.generator import RepairCase, RepairPlan


@dataclass(frozen=True, slots=True)
class PatchGuardPolicy:
    """Limits that a generated patch must satisfy before execution."""

    max_files: int = 1
    max_added_lines: int = 8
    max_removed_lines: int = 4
    allowed_suffixes: tuple[str, ...] = (".py",)
    forbidden_prefixes: tuple[str, ...] = (
        ".github/",
        "config/",
        "scripts/",
        "src/modelguard/",
    )
    forbidden_tokens: tuple[str, ...] = (
        "eval(",
        "exec(",
        "os.system(",
        "subprocess.",
        "requests.",
        "socket.",
        "__import__(",
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PatchGuardDecision:
    """Result of evaluating a plan against static repair policy."""

    approved: bool
    checks: tuple[str, ...]
    violations: tuple[str, ...]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_patch_guard(
    plan: RepairPlan,
    case: RepairCase,
    policy: PatchGuardPolicy | None = None,
) -> PatchGuardDecision:
    """Approve only minimal, path-safe and non-dangerous patch proposals."""
    policy = policy or PatchGuardPolicy()
    checks: list[str] = []
    violations: list[str] = []

    if plan.confidence == "high" and plan.score >= 0.8:
        checks.append("leading diagnosis has high confidence and score >= 0.8")
    else:
        violations.append("leading diagnosis does not meet the repair confidence gate")

    if len(plan.patches) <= policy.max_files:
        checks.append(f"patch changes at most {policy.max_files} file(s)")
    else:
        violations.append(f"patch changes more than {policy.max_files} file(s)")

    for patch in plan.patches:
        path = PurePosixPath(patch.path)
        if path.is_absolute() or ".." in path.parts:
            violations.append(f"unsafe patch path: {patch.path}")
        else:
            checks.append(f"path is relative and traversal-safe: {patch.path}")
        if patch.path != case.target_file:
            violations.append(f"patch path does not match repair case: {patch.path}")
        if not any(patch.path.startswith(prefix) for prefix in case.allowed_paths):
            violations.append(f"patch path is outside allowed prefixes: {patch.path}")
        if any(patch.path.startswith(prefix) for prefix in policy.forbidden_prefixes):
            violations.append(f"patch targets a protected repository area: {patch.path}")
        if path.suffix not in policy.allowed_suffixes:
            violations.append(f"unsupported patched file type: {path.suffix}")
        if patch.added_lines > policy.max_added_lines:
            violations.append(f"patch adds too many lines: {patch.added_lines}")
        if patch.removed_lines > policy.max_removed_lines:
            violations.append(f"patch removes too many lines: {patch.removed_lines}")
        if patch.original_sha256 == patch.patched_sha256:
            violations.append("patch does not change file content")
        added_text = "\n".join(
            line[1:]
            for line in patch.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        for token in policy.forbidden_tokens:
            if token in added_text:
                violations.append(f"patch introduces forbidden token: {token}")
        if not violations:
            checks.append(f"line and token limits pass for {patch.path}")

    return PatchGuardDecision(
        approved=not violations,
        checks=tuple(checks),
        violations=tuple(violations),
        policy=policy.to_dict(),
    )
