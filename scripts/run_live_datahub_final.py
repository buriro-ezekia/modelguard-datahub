#!/usr/bin/env python3
# Run the final resilient DataHub verification and prove model-deployment
# lineage in both graph directions.
"""Verify live SDK, MCP, ML lineage, deployment linkage and incident write-back."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import run_live_datahub_complete as startup
import run_live_datahub_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = evidence.ARTIFACTS


def _relationship_evidence(
    *,
    model_snapshot: dict[str, Any],
    deployment_snapshot: dict[str, Any],
    model_urn: str,
    deployment_urn: str,
) -> dict[str, Any]:
    """Verify one graph edge using either equivalent lineage direction."""

    model_context_urns = evidence._all_urns(model_snapshot)
    deployment_context_urns = evidence._all_urns(deployment_snapshot)
    forward = deployment_urn in model_context_urns
    reverse = model_urn in deployment_context_urns

    if forward and reverse:
        direction = "both"
    elif forward:
        direction = "model_downstream"
    elif reverse:
        direction = "deployment_upstream"
    else:
        direction = "not_observed"

    return {
        "verified": forward or reverse,
        "verification_direction": direction,
        "model_downstream_contains_deployment": forward,
        "deployment_upstream_contains_model": reverse,
        "model_context_observed_urns": sorted(model_context_urns),
        "deployment_context_observed_urns": sorted(deployment_context_urns),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-start-datahub",
        action="store_true",
        help="Do not start a local DataHub quickstart when GMS is unavailable.",
    )
    parser.add_argument(
        "--datahub-version",
        default=None,
        help="Optional DataHub quickstart version passed to datahub docker quickstart.",
    )
    parser.add_argument(
        "--gms-timeout-seconds",
        type=int,
        default=300,
        help="Maximum time to wait for GMS after quickstart returns.",
    )
    parser.add_argument("--install-mcp-server", action="store_true")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--external-mcp", action="store_true")
    parser.add_argument("--mcp-url", default=evidence.DEFAULT_MCP_URL)
    parser.add_argument("--mcp-health-url", default=evidence.DEFAULT_MCP_HEALTH_URL)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.gms_timeout_seconds < 10:
        parser.error("--gms-timeout-seconds must be at least 10")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("DATAHUB_GMS_URL", "http://localhost:8080")
    env["MODELGUARD_DATAHUB_PROVIDER"] = "sdk"

    mcp_process = None
    mcp_log_handle = None

    try:
        print("===== ENSURING DATAHUB IS READY =====")
        startup._ensure_datahub(
            env=env,
            start_local=not args.no_start_datahub,
            version=args.datahub_version,
            timeout_seconds=args.gms_timeout_seconds,
        )

        print("\n===== LOADING LIVE ML LINEAGE =====")
        manifest_path = ARTIFACTS / "ml_lineage_manifest.json"
        evidence._run(
            [
                sys.executable,
                "scripts/load_live_ml_lineage.py",
                "--output",
                str(manifest_path),
            ],
            env=env,
            output_log=ARTIFACTS / "ml_lineage_load.log",
        )
        manifest = evidence._read_json(manifest_path)
        model_urn = str(manifest["model_urn"])
        deployment_urn = str(manifest["deployment_urn"])

        print("\n===== VERIFYING LIVE SDK CONTEXT =====")
        sdk_training_path = ARTIFACTS / "sdk_training_context.json"
        sdk_model_path = ARTIFACTS / "sdk_model_context.json"
        sdk_deployment_path = ARTIFACTS / "sdk_deployment_context.json"
        sdk_training = evidence._collect_with_retry(
            provider="sdk",
            urn=str(manifest["training_dataset_urn"]),
            output=sdk_training_path,
            env=env,
            require_upstream=True,
            require_downstream=True,
        )
        sdk_model = evidence._collect_with_retry(
            provider="sdk",
            urn=model_urn,
            output=sdk_model_path,
            env=env,
            require_upstream=True,
            require_downstream=False,
        )
        sdk_deployment = evidence._collect_with_retry(
            provider="sdk",
            urn=deployment_urn,
            output=sdk_deployment_path,
            env=env,
            require_upstream=True,
            require_downstream=False,
        )

        mcp_env = dict(env)
        mcp_env["DATAHUB_MCP_URL"] = args.mcp_url
        mcp_env["MODELGUARD_DATAHUB_PROVIDER"] = "mcp"
        if not mcp_env.get("DATAHUB_MCP_TOKEN") and mcp_env.get("DATAHUB_GMS_TOKEN"):
            mcp_env["DATAHUB_MCP_TOKEN"] = mcp_env["DATAHUB_GMS_TOKEN"]

        if not args.external_mcp:
            print("\n===== STARTING SELF-HOSTED DATAHUB MCP SERVER =====")
            mcp_process, mcp_log_handle = evidence._start_mcp_server(
                env=mcp_env,
                install=args.install_mcp_server,
                health_url=args.mcp_health_url,
            )

        print("\n===== VERIFYING LIVE MCP CONTEXT =====")
        evidence._run(
            [sys.executable, "-m", "modelguard", "context", "check", "--provider", "mcp"],
            env=mcp_env,
            output_log=ARTIFACTS / "mcp_connection_check.log",
        )
        mcp_training_path = ARTIFACTS / "mcp_training_context.json"
        mcp_model_path = ARTIFACTS / "mcp_model_context.json"
        mcp_deployment_path = ARTIFACTS / "mcp_deployment_context.json"
        mcp_training = evidence._collect_with_retry(
            provider="mcp",
            urn=str(manifest["training_dataset_urn"]),
            output=mcp_training_path,
            env=mcp_env,
            require_upstream=True,
            require_downstream=True,
        )
        mcp_model = evidence._collect_with_retry(
            provider="mcp",
            urn=model_urn,
            output=mcp_model_path,
            env=mcp_env,
            require_upstream=True,
            require_downstream=False,
        )
        mcp_deployment = evidence._collect_with_retry(
            provider="mcp",
            urn=deployment_urn,
            output=mcp_deployment_path,
            env=mcp_env,
            require_upstream=True,
            require_downstream=False,
        )

        print("\n===== VERIFYING LIVE DATAHUB WRITE-BACK =====")
        first_receipt, repeat_receipt = evidence._publish_live_incident(
            manifest=manifest,
            env=env,
        )

        expected_downstream = {
            str(manifest["monthly_spend_feature_urn"]),
            str(manifest["account_age_feature_urn"]),
            model_urn,
        }
        sdk_training_urns = evidence._all_urns(sdk_training.get("downstream") or [])
        mcp_training_urns = evidence._all_urns(mcp_training.get("downstream") or [])
        sdk_link = _relationship_evidence(
            model_snapshot=sdk_model,
            deployment_snapshot=sdk_deployment,
            model_urn=model_urn,
            deployment_urn=deployment_urn,
        )
        mcp_link = _relationship_evidence(
            model_snapshot=mcp_model,
            deployment_snapshot=mcp_deployment,
            model_urn=model_urn,
            deployment_urn=deployment_urn,
        )

        relationship_path = ARTIFACTS / "model_deployment_relationship.json"
        evidence._write_json(
            relationship_path,
            {
                "model_urn": model_urn,
                "deployment_urn": deployment_urn,
                "sdk": sdk_link,
                "mcp": mcp_link,
            },
        )

        first_datahub = evidence._channel(first_receipt, "datahub")
        repeat_datahub = evidence._channel(repeat_receipt, "datahub")
        checks = {
            "sdk_provider_verified": sdk_training.get("provider") == "sdk",
            "mcp_provider_verified": mcp_training.get("provider") == "mcp",
            "sdk_ml_lineage_verified": bool(sdk_training_urns & expected_downstream),
            "mcp_ml_lineage_verified": bool(mcp_training_urns & expected_downstream),
            "sdk_model_deployment_link_verified": bool(sdk_link["verified"]),
            "mcp_model_deployment_link_verified": bool(mcp_link["verified"]),
            "live_datahub_writeback_verified": first_datahub.get("status")
            in {"published", "noop"},
            "live_datahub_writeback_idempotent": repeat_datahub.get("action") == "noop",
        }

        summary = {
            "status": "complete" if all(checks.values()) else "failed",
            "datahub_gms_url": env["DATAHUB_GMS_URL"],
            "mcp_url": args.mcp_url,
            "mcp_server_version": evidence.MCP_SERVER_VERSION,
            "training_dataset_urn": manifest["training_dataset_urn"],
            "model_urn": model_urn,
            "deployment_urn": deployment_urn,
            "sdk_training_context": {
                "schema_fields": len((sdk_training.get("entity") or {}).get("schema_fields") or []),
                "upstream_assets": len(sdk_training.get("upstream") or []),
                "downstream_assets": len(sdk_training.get("downstream") or []),
            },
            "mcp_training_context": {
                "schema_fields": len((mcp_training.get("entity") or {}).get("schema_fields") or []),
                "upstream_assets": len(mcp_training.get("upstream") or []),
                "downstream_assets": len(mcp_training.get("downstream") or []),
            },
            "model_deployment_relationship": {
                "sdk_direction": sdk_link["verification_direction"],
                "mcp_direction": mcp_link["verification_direction"],
            },
            "datahub_writeback": {
                "first_action": first_datahub.get("action"),
                "repeat_action": repeat_datahub.get("action"),
                "incident_urn": first_datahub.get("external_id")
                or repeat_datahub.get("external_id"),
            },
            "checks": checks,
        }
        summary_path = ARTIFACTS / "complete_summary.json"
        evidence._write_json(summary_path, summary)

        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RuntimeError(
                "live verification checks failed: "
                + ", ".join(failed)
                + f"; inspect {relationship_path}"
            )

        promoted: list[str] = []
        if args.promote:
            promoted = evidence._promote(
                {
                    "ml_lineage_manifest": manifest_path,
                    "sdk_ml_context": sdk_training_path,
                    "mcp_ml_context": mcp_training_path,
                    "sdk_model_context": sdk_model_path,
                    "mcp_model_context": mcp_model_path,
                    "sdk_deployment_context": sdk_deployment_path,
                    "mcp_deployment_context": mcp_deployment_path,
                    "model_deployment_relationship": relationship_path,
                    "writeback_first": ARTIFACTS / "datahub_writeback_first.json",
                    "writeback_repeat": ARTIFACTS / "datahub_writeback_repeat.json",
                    "complete_summary": summary_path,
                }
            )

        print("\nLIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED")
        print(json.dumps(summary, indent=2, sort_keys=True))
        if promoted:
            print("\nPromoted evidence:")
            for path in promoted:
                print(f"- {path}")
        return 0
    except Exception as exc:
        startup._collect_diagnostics(env=env)
        print(f"\nLIVE DATAHUB VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        evidence._stop_mcp_server(mcp_process, mcp_log_handle)


if __name__ == "__main__":
    raise SystemExit(main())
