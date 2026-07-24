from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_submission_assets_validate() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_submission.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(
        (ROOT / "artifacts/submission_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "ready_except_public_video_url"
    assert manifest["manual_final_fields"] == ["public_video_url"]


def test_hosted_demo_has_core_verified_claims() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    for claim in (
        "0.771",
        "0.842",
        "H001",
        "delivery-43a1891cc0d4",
        "raised_and_resolved",
    ):
        assert claim in html
