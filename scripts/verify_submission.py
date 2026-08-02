#!/usr/bin/env python3
"""Verify that the judge-facing submission assets are internally complete."""

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
    "submission/LIVE_DATAHUB_EVIDENCE.md",
    "submission/RELEASE_CHECKLIST.md",
    "scripts/run_showcase.py",
    "scripts/load_live_ml_lineage.py",
    "scripts/run_live_datahub_evidence.py",
    "examples/live_datahub_context.json",
    "examples/live_datahub_selection_summary.json",
    "examples/live_datahub_verification_summary.json",
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

    required_links = (
        "https://buriro-ezekia.github.io/modelguard-datahub/",
        "https://github.com/buriro-ezekia/modelguard-datahub",
        "https://youtu.be/S96pbK7k_nc",
    )
    missing_links = [link for link in required_links if link not in draft]
    if missing_links:
        raise SystemExit("missing final submission links: " + ", ".join(missing_links))

    live_sdk = json.loads(
        (ROOT / "examples/live_datahub_verification_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if live_sdk.get("provider") != "sdk":
        raise SystemExit("committed live DataHub evidence must use the SDK provider")
    if int(live_sdk.get("upstream_assets", 0)) < 1:
        raise SystemExit("committed live SDK evidence must include upstream lineage")
    if int(live_sdk.get("downstream_assets", 0)) < 1:
        raise SystemExit("committed live SDK evidence must include downstream lineage")

    optional_complete = ROOT / "examples/live_datahub_complete_summary.json"
    complete_live_evidence = optional_complete.is_file()
    if complete_live_evidence:
        summary = json.loads(optional_complete.read_text(encoding="utf-8"))
        checks = summary.get("checks") or {}
        failed = [name for name, passed in checks.items() if passed is not True]
        if summary.get("status") != "complete" or failed:
            raise SystemExit(
                "promoted live DataHub evidence is incomplete: " + ", ".join(failed)
            )

    manifest = {
        "status": "ready",
        "required_assets": len(REQUIRED),
        "hosted_site_url": "https://buriro-ezekia.github.io/modelguard-datahub/",
        "public_video_url": "https://youtu.be/S96pbK7k_nc",
        "committed_live_sdk_evidence": True,
        "complete_live_sdk_mcp_ml_evidence": complete_live_evidence,
        "manual_final_checks": [
            "open hosted site in a private browser window",
            "play the public video without signing in",
            "confirm Apache-2.0 is visible in the repository About section",
        ],
    }
    output = ROOT / "artifacts/submission_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
