"""Human-readable ModelGuard reports."""

from modelguard.reporting.markdown import render_diagnosis_markdown
from modelguard.reporting.repair import render_repair_markdown

__all__ = ["render_diagnosis_markdown", "render_repair_markdown"]
