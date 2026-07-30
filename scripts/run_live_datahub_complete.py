#!/usr/bin/env python3
# Ensure DataHub is reachable, start a local quickstart when needed,
# capture diagnostics and run the live ModelGuard evidence workflow.
"""Run the complete live ModelGuard verification with resilient DataHub startup."""

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
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/live_datahub_complete"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
KEY_CONTAINERS = (
    "datahub-datahub-gms-quickstart-1",
    "datahub-system-update-quickstart-1",
    "datahub-opensearch-1",
    "datahub-mysql-1",
    "datahub-kafka-broker-1",
    "datahub-datahub-actions-quickstart-1",
)


def _find_executable(name: str) -> str | None:
    executable = shutil.which(name)
    if executable:
        return executable
    candidate = Path(sysconfig.get_path("scripts")) / name
    return str(candidate) if candidate.is_file() else None


def _is_local_url(url: str) -> bool:
    return (parse.urlsplit(url).hostname or "").lower() in LOCAL_HOSTS


def _headers(env: dict[str, str]) -> dict[str, str]:
    token = env.get("DATAHUB_GMS_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _http_ready(url: str, *, env: dict[str, str]) -> bool:
    try:
        req = request.Request(url, headers=_headers(env))
        with request.urlopen(req, timeout=4) as response:
            return 200 <= response.status < 300
    except (error.URLError, TimeoutError, ValueError):
        return False


def _gms_endpoints(gms_url: str) -> tuple[str, str]:
    base = gms_url.rstrip("/")
    return f"{base}/health", f"{base}/config"


def _gms_ready(gms_url: str, *, env: dict[str, str]) -> bool:
    return any(_http_ready(url, env=env) for url in _gms_endpoints(gms_url))


def _write_command_result(
    path: Path,
    command: list[str],
    completed: subprocess.CompletedProcess[str] | None,
    failure: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["COMMAND: " + " ".join(command), ""]
    if completed is not None:
        lines.extend(
            [
                f"RETURN CODE: {completed.returncode}",
                "",
                "STDOUT",
                completed.stdout,
                "",
                "STDERR",
                completed.stderr,
            ]
        )
    if failure:
        lines.extend(["", "FAILURE", failure])
    path.write_text("\n".join(lines), encoding="utf-8")


def _capture(
    name: str,
    command: list[str],
    *,
    env: dict[str, str],
    timeout: int = 60,
) -> subprocess.CompletedProcess[str] | None:
    path = ARTIFACTS / f"{name}.log"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        _write_command_result(path, command, completed)
        return completed
    except (OSError, subprocess.TimeoutExpired) as exc:
        _write_command_result(path, command, None, str(exc))
        return None


def _collect_diagnostics(*, env: dict[str, str]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    docker = _find_executable("docker")
    datahub = _find_executable("datahub")

    if docker:
        _capture(
            "docker_ps",
            [
                docker,
                "ps",
                "-a",
                "--filter",
                "name=datahub",
                "--format",
                "table {{.Names}}\t{{.Image}}\t{{.Status}}",
            ],
            env=env,
        )
        _capture("docker_stats", [docker, "stats", "--no-stream"], env=env)
        for container in KEY_CONTAINERS:
            slug = container.replace("datahub-", "").replace("-quickstart-1", "")
            _capture(
                f"inspect_{slug}",
                [
                    docker,
                    "inspect",
                    "--format",
                    (
                        "name={{.Name}} image={{.Config.Image}} status={{.State.Status}} "
                        "exit={{.State.ExitCode}} oom={{.State.OOMKilled}} "
                        "health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
                    ),
                    container,
                ],
                env=env,
            )
            _capture(
                f"logs_{slug}",
                [docker, "logs", "--tail", "200", container],
                env=env,
            )

    if datahub:
        _capture("datahub_docker_check", [datahub, "docker", "check"], env=env)

    summary = {
        "status": "diagnostics_captured",
        "datahub_gms_url": env.get("DATAHUB_GMS_URL"),
        "docker_available": docker is not None,
        "datahub_cli_available": datahub is not None,
        "files": sorted(path.name for path in ARTIFACTS.glob("*.log")),
    }
    (ARTIFACTS / "startup_diagnostics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _start_quickstart(*, env: dict[str, str], version: str | None) -> None:
    docker = _find_executable("docker")
    datahub = _find_executable("datahub")
    if docker is None:
        raise RuntimeError("Docker is unavailable; a local DataHub quickstart cannot be started.")
    if datahub is None:
        raise RuntimeError(
            'The DataHub CLI is unavailable. Install the live dependencies with: '
            'python -m pip install -e ".[dev,live]"'
        )

    docker_check = _capture("docker_info", [docker, "info"], env=env)
    if docker_check is None or docker_check.returncode != 0:
        raise RuntimeError(
            f"Docker is not ready. Inspect {ARTIFACTS / 'docker_info.log'}."
        )

    command = [datahub, "docker", "quickstart", "--dump-logs-on-failure"]
    if version:
        command.extend(["--version", version])

    print("DataHub GMS is offline; starting the local DataHub quickstart...")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    _write_command_result(ARTIFACTS / "datahub_quickstart.log", command, completed)
    if completed.returncode != 0:
        _collect_diagnostics(env=env)
        raise RuntimeError(
            "DataHub quickstart failed. Inspect "
            f"{ARTIFACTS / 'datahub_quickstart.log'} and startup diagnostics."
        )


def _wait_for_gms(gms_url: str, *, env: dict[str, str], timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        if _gms_ready(gms_url, env=env):
            print(f"DataHub GMS is ready at {gms_url}.")
            return
        if attempt == 1 or attempt % 10 == 0:
            print(f"Waiting for DataHub GMS at {gms_url} (attempt {attempt})...")
        time.sleep(2)
    _collect_diagnostics(env=env)
    raise RuntimeError(
        f"DataHub GMS did not become ready within {timeout_seconds} seconds. "
        f"Inspect {ARTIFACTS}."
    )


def _ensure_datahub(
    *,
    env: dict[str, str],
    start_local: bool,
    version: str | None,
    timeout_seconds: int,
) -> None:
    gms_url = env["DATAHUB_GMS_URL"].rstrip("/")
    if _gms_ready(gms_url, env=env):
        print(f"Using the existing DataHub GMS at {gms_url}.")
        return

    if not _is_local_url(gms_url):
        raise RuntimeError(
            f"The configured remote DataHub GMS is unreachable: {gms_url}. "
            "Check the URL, network access and DATAHUB_GMS_TOKEN."
        )

    if not start_local:
        _collect_diagnostics(env=env)
        raise RuntimeError(
            f"Local DataHub GMS is not reachable at {gms_url}. "
            "Rerun without --no-start-datahub or start it with "
            "datahub docker quickstart."
        )

    _start_quickstart(env=env, version=version)
    _wait_for_gms(gms_url, env=env, timeout_seconds=timeout_seconds)


def _evidence_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, "scripts/run_live_datahub_evidence.py"]
    if args.install_mcp_server:
        command.append("--install-mcp-server")
    if args.promote:
        command.append("--promote")
    if args.external_mcp:
        command.append("--external-mcp")
    if args.mcp_url:
        command.extend(["--mcp-url", args.mcp_url])
    if args.mcp_health_url:
        command.extend(["--mcp-health-url", args.mcp_health_url])
    return command


def main() -> int:
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
        help="Maximum time to wait for local GMS after quickstart returns.",
    )
    parser.add_argument("--install-mcp-server", action="store_true")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--external-mcp", action="store_true")
    parser.add_argument("--mcp-url", default=None)
    parser.add_argument("--mcp-health-url", default=None)
    args = parser.parse_args()

    if args.gms_timeout_seconds < 10:
        parser.error("--gms-timeout-seconds must be at least 10")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("DATAHUB_GMS_URL", "http://localhost:8080")

    try:
        print("===== ENSURING DATAHUB IS READY =====")
        _ensure_datahub(
            env=env,
            start_local=not args.no_start_datahub,
            version=args.datahub_version,
            timeout_seconds=args.gms_timeout_seconds,
        )
        print("\n===== RUNNING COMPLETE LIVE EVIDENCE =====")
        completed = subprocess.run(
            _evidence_command(args),
            cwd=ROOT,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            _collect_diagnostics(env=env)
        return completed.returncode
    except Exception as exc:
        print(f"\nLIVE DATAHUB STARTUP FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
