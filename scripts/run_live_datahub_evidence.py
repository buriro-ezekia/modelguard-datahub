#!/usr/bin/env python3
"""Verify live DataHub SDK, MCP, ML lineage and incident write-back end to end."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/live_datahub_complete"
MCP_SERVER_VERSION = "0.6.0"
DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_MCP_HEALTH_URL = "http://127.0.0.1:8000/health"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(
    arguments: list[str],
    *,
    env: dict[str, str],
    output_log: Path | None = None,
    expected: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    allowed = expected or {0}
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if output_log is not None:
        output_log.parent.mkdir(parents=True, exist_ok=True)
        output_log.write_text(
            "COMMAND: "
            + " ".join(arguments)
            + "\n\nSTDOUT\n"
            + completed.stdout
            + "\nSTDERR\n"
            + completed.stderr,
            encoding="utf-8",
        )
    if completed.returncode not in allowed:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(arguments)}\n"
            f"stdout:\n{completed.stdout[-2000:]}\n"
            f"stderr:\n{completed.stderr[-2000:]}"
        )
    return completed


def _http_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=3) as response:
            return 200 <= response.status < 300
    except (error.URLError, TimeoutError, ValueError):
        return False


def _wait_for_http(url: str, *, process: subprocess.Popen[str] | None = None) -> None:
    for _ in range(60):
        if _http_ready(url):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"MCP server exited with code {process.returncode}; "
                f"inspect {ARTIFACTS / 'mcp_server.log'}"
            )
        time.sleep(1)
    raise RuntimeError(f"service did not become ready: {url}")


def _mcp_command(*, install: bool, env: dict[str, str]) -> list[str]:
    executable = shutil.which("mcp-server-datahub")
    if executable:
        return [executable, "--transport", "http"]

    uvx = shutil.which("uvx")
    if uvx:
        return [
            uvx,
            "--from",
            f"mcp-server-datahub=={MCP_SERVER_VERSION}",
            "mcp-server-datahub",
            "--transport",
            "http",
        ]

    if not install:
        raise RuntimeError(
            "The DataHub MCP Server is unavailable. Install uv/uvx or rerun with "
            "--install-mcp-server to install the pinned server package."
        )

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"mcp-server-datahub=={MCP_SERVER_VERSION}",
        ],
        env=env,
        output_log=ARTIFACTS / "mcp_server_install.log",
    )
    executable = shutil.which("mcp-server-datahub")
    if executable is None:
        scripts_directory = Path(sysconfig.get_path("scripts"))
        candidate = scripts_directory / "mcp-server-datahub"
        executable = str(candidate) if candidate.is_file() else None
    if executable is None:
        raise RuntimeError("mcp-server-datahub was installed but its executable was not found")
    return [executable, "--transport", "http"]


def _start_mcp_server(
    *,
    env: dict[str, str],
    install: bool,
    health_url: str,
) -> tuple[subprocess.Popen[str] | None, Any | None]:
    if _http_ready(health_url):
        print(f"Using the existing MCP server at {health_url}")
        return None, None

    command = _mcp_command(install=install, env=env)
    log_path = ARTIFACTS / "mcp_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_for_http(health_url, process=process)
    print(f"Started DataHub MCP Server {MCP_SERVER_VERSION}")
    return process, log_handle


def _stop_mcp_server(process: subprocess.Popen[str] | None, log_handle: Any | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if log_handle is not None:
        log_handle.close()


def _context_command(provider: str, urn: str, output: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "modelguard",
        "context",
        "collect",
        "--provider",
        provider,
        "--urn",
        urn,
        "--lineage-direction",
        "both",
        "--output",
        str(output),
    ]


def _collect_with_retry(
    *,
    provider: str,
    urn: str,
    output: Path,
    env: dict[str, str],
    require_upstream: bool,
    require_downstream: bool,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, 31):
        completed = subprocess.run(
            _context_command(provider, urn, output),
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0 and output.is_file():
            snapshot = _read_json(output)
            upstream = snapshot.get("upstream") or []
            downstream = snapshot.get("downstream") or []
            upstream_ready = bool(upstream) or not require_upstream
            downstream_ready = bool(downstream) or not require_downstream
            print(
                f"[{attempt:02d}/30] {provider} {urn.split(':', 3)[2]}: "
                f"upstream={len(upstream)} downstream={len(downstream)}"
            )
            if upstream_ready and downstream_ready:
                return snapshot
            last_error = "lineage has not been indexed yet"
        else:
            last_error = (completed.stderr or completed.stdout)[-1200:]
            print(f"[{attempt:02d}/30] {provider} context not ready")
        time.sleep(4)
    raise RuntimeError(
        f"{provider} context did not become ready for {urn}: {last_error}"
    )


def _all_urns(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "urn" and isinstance(item, str):
                output.add(item)
            output.update(_all_urns(item))
    elif isinstance(value, list):
        for item in value:
            output.update(_all_urns(item))
    elif isinstance(value, str) and value.startswith("urn:li:"):
        output.add(value)
    return output


def _channel(receipt: dict[str, Any], name: str) -> dict[str, Any]:
    for channel in receipt.get("channels") or []:
        if isinstance(channel, dict) and channel.get("channel") == name:
            return channel
    raise RuntimeError(f"publication receipt is missing the {name} channel")


def _publish_live_incident(
    *,
    manifest: dict[str, Any],
    env: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    showcase = ROOT / "artifacts/showcase"
    _run(
        [sys.executable, "scripts/run_showcase.py"],
        env=env,
        output_log=ARTIFACTS / "showcase.log",
    )

    publish_env = dict(env)
    gms_url = publish_env.get("DATAHUB_GMS_URL", "")
    if not publish_env.get("DATAHUB_GRAPHQL_TOKEN") and not publish_env.get(
        "DATAHUB_GMS_TOKEN"
    ):
        if gms_url.startswith(("http://localhost", "http://127.0.0.1")):
            publish_env["DATAHUB_GRAPHQL_TOKEN"] = "modelguard-local-quickstart"

    common = [
        sys.executable,
        "-m",
        "modelguard",
        "publish",
        "--diagnosis",
        str(showcase / "diagnosis_report.json"),
        "--repair-plan",
        str(showcase / "repair_plan.json"),
        "--validation",
        str(showcase / "repair_validation.json"),
        "--patch",
        str(showcase / "validated_patch.diff"),
        "--datahub-asset-urn",
        str(manifest["feature_dataset_urn"]),
        "--github-mode",
        "off",
        "--datahub-mode",
        "live",
        "--apply",
    ]
    first_path = ARTIFACTS / "datahub_writeback_first.json"
    repeat_path = ARTIFACTS / "datahub_writeback_repeat.json"

    _run(
        [*common, "--output", str(first_path)],
        env=publish_env,
        output_log=ARTIFACTS / "datahub_writeback_first.log",
    )
    _run(
        [*common, "--output", str(repeat_path)],
        env=publish_env,
        output_log=ARTIFACTS / "datahub_writeback_repeat.log",
    )
    return _read_json(first_path), _read_json(repeat_path)


def _promote(paths: dict[str, Path]) -> list[str]:
    examples = ROOT / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    promoted: list[str] = []
    for name, source in paths.items():
        target = examples / f"live_datahub_{name}.json"
        payload = _read_json(source)
        _write_json(target, payload)
        promoted.append(str(target.relative_to(ROOT)))
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install-mcp-server",
        action="store_true",
        help=f"Install mcp-server-datahub=={MCP_SERVER_VERSION} when unavailable.",
    )
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--mcp-health-url", default=DEFAULT_MCP_HEALTH_URL)
    parser.add_argument(
        "--external-mcp",
        action="store_true",
        help="Use an already managed MCP endpoint instead of starting a local server.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Copy the sanitised successful evidence into examples/.",
    )
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("DATAHUB_GMS_URL", "http://localhost:8080")
    env["MODELGUARD_DATAHUB_PROVIDER"] = "sdk"

    process: subprocess.Popen[str] | None = None
    log_handle: Any | None = None
    try:
        print("===== LOADING LIVE ML LINEAGE =====")
        manifest_path = ARTIFACTS / "ml_lineage_manifest.json"
        _run(
            [
                sys.executable,
                "scripts/load_live_ml_lineage.py",
                "--output",
                str(manifest_path),
            ],
            env=env,
            output_log=ARTIFACTS / "ml_lineage_load.log",
        )
        manifest = _read_json(manifest_path)

        print("\n===== VERIFYING LIVE SDK CONTEXT =====")
        sdk_training_path = ARTIFACTS / "sdk_training_context.json"
        sdk_model_path = ARTIFACTS / "sdk_model_context.json"
        sdk_training = _collect_with_retry(
            provider="sdk",
            urn=str(manifest["training_dataset_urn"]),
            output=sdk_training_path,
            env=env,
            require_upstream=True,
            require_downstream=True,
        )
        sdk_model = _collect_with_retry(
            provider="sdk",
            urn=str(manifest["model_urn"]),
            output=sdk_model_path,
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
            process, log_handle = _start_mcp_server(
                env=mcp_env,
                install=args.install_mcp_server,
                health_url=args.mcp_health_url,
            )

        print("\n===== VERIFYING LIVE MCP CONTEXT =====")
        _run(
            [sys.executable, "-m", "modelguard", "context", "check", "--provider", "mcp"],
            env=mcp_env,
            output_log=ARTIFACTS / "mcp_connection_check.log",
        )
        mcp_training_path = ARTIFACTS / "mcp_training_context.json"
        mcp_model_path = ARTIFACTS / "mcp_model_context.json"
        mcp_training = _collect_with_retry(
            provider="mcp",
            urn=str(manifest["training_dataset_urn"]),
            output=mcp_training_path,
            env=mcp_env,
            require_upstream=True,
            require_downstream=True,
        )
        mcp_model = _collect_with_retry(
            provider="mcp",
            urn=str(manifest["model_urn"]),
            output=mcp_model_path,
            env=mcp_env,
            require_upstream=True,
            require_downstream=False,
        )

        print("\n===== VERIFYING LIVE DATAHUB WRITE-BACK =====")
        first_receipt, repeat_receipt = _publish_live_incident(
            manifest=manifest,
            env=env,
        )

        expected_downstream = {
            str(manifest["monthly_spend_feature_urn"]),
            str(manifest["account_age_feature_urn"]),
            str(manifest["model_urn"]),
        }
        sdk_training_urns = _all_urns(sdk_training.get("downstream") or [])
        mcp_training_urns = _all_urns(mcp_training.get("downstream") or [])
        deployment_urn = str(manifest["deployment_urn"])
        sdk_model_urns = _all_urns(sdk_model)
        mcp_model_urns = _all_urns(mcp_model)

        first_datahub = _channel(first_receipt, "datahub")
        repeat_datahub = _channel(repeat_receipt, "datahub")
        checks = {
            "sdk_provider_verified": sdk_training.get("provider") == "sdk",
            "mcp_provider_verified": mcp_training.get("provider") == "mcp",
            "sdk_ml_lineage_verified": bool(sdk_training_urns & expected_downstream),
            "mcp_ml_lineage_verified": bool(mcp_training_urns & expected_downstream),
            "sdk_model_deployment_link_verified": deployment_urn in sdk_model_urns,
            "mcp_model_deployment_link_verified": deployment_urn in mcp_model_urns,
            "live_datahub_writeback_verified": first_datahub.get("status")
            in {"published", "noop"},
            "live_datahub_writeback_idempotent": repeat_datahub.get("action") == "noop",
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise RuntimeError("live verification checks failed: " + ", ".join(failed))

        summary = {
            "status": "complete",
            "datahub_gms_url": env["DATAHUB_GMS_URL"],
            "mcp_url": args.mcp_url,
            "mcp_server_version": MCP_SERVER_VERSION,
            "training_dataset_urn": manifest["training_dataset_urn"],
            "model_urn": manifest["model_urn"],
            "deployment_urn": manifest["deployment_urn"],
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
            "datahub_writeback": {
                "first_action": first_datahub.get("action"),
                "repeat_action": repeat_datahub.get("action"),
                "incident_urn": first_datahub.get("external_id")
                or repeat_datahub.get("external_id"),
            },
            "checks": checks,
        }
        summary_path = ARTIFACTS / "complete_summary.json"
        _write_json(summary_path, summary)

        promoted: list[str] = []
        if args.promote:
            promoted = _promote(
                {
                    "ml_lineage_manifest": manifest_path,
                    "sdk_ml_context": sdk_training_path,
                    "mcp_ml_context": mcp_training_path,
                    "sdk_model_context": sdk_model_path,
                    "mcp_model_context": mcp_model_path,
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
        print(f"\nLIVE DATAHUB VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        _stop_mcp_server(process, log_handle)


if __name__ == "__main__":
    raise SystemExit(main())
