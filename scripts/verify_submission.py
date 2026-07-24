#!/usr/bin/env python3
"""Verify that the judge-facing Phase 6 submission assets are internally complete."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "docs/index.html",
    "docs/styles.css",
    "docs/app.js",
    "docs/assets/architecture.svg",
    "docs/assets/screenshot-overview.svg",
    "docs/assets/screenshot-evidence.svg",
    "docs/assets/screenshot-mobile.svg",
    "submission/DEVPOST_DRAFT.md",
    "submission/DEMO_SCRIPT.md",
    "submission/JUDGING_GUIDE.md",
    "submission/TESTING_INSTRUCTIONS.md",
    "submission/RELEASE_CHECKLIST.md",
    "scripts/run_showcase.py",
)


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit("missing submission assets: " + ", ".join(missing))

    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    for reference in re.findall(r'(?:src|href)="([^"]+)"', html):
        if reference.startswith(("http://", "https://", "#")):
            continue
        target = (ROOT / "docs" / reference.split("?", 1)[0]).resolve()
        docs_root = ROOT / "docs"
        if docs_root not in target.parents and target != docs_root:
            raise SystemExit(f"unsafe site reference: {reference}")
        if not target.exists():
            raise SystemExit(f"broken site reference: {reference}")

    draft = (ROOT / "submission/DEVPOST_DRAFT.md").read_text(encoding="utf-8")
    required_headings = (
        "## Elevator pitch",
        "## Inspiration",
        "## What it does",
        "## How we built it",
        "## Challenges we ran into",
        "## Accomplishments",
        "## What we learned",
        "## What's next",
        "## Built with",
        "## Final submission fields",
    )
    missing_headings = [heading for heading in required_headings if heading not in draft]
    if missing_headings:
        raise SystemExit("missing Devpost sections: " + ", ".join(missing_headings))

    manifest = {
        "status": "ready_except_public_video_url",
        "required_assets": len(REQUIRED),
        "hosted_site_expected_url": (
            "https://buriro-ezekia.github.io/modelguard-datahub/"
        ),
        "manual_final_fields": ["public_video_url"],
    }
    output = ROOT / "artifacts/submission_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
