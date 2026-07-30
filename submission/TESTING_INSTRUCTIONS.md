# Testing Instructions

## Option A — Hosted demonstration

Open:

```text
https://buriro-ezekia.github.io/modelguard-datahub/
```

Use **Replay the incident** or select the six terminal stages individually. The page is static, requires no login and does not collect data.

## Option B — GitHub Codespaces

1. Open the repository in Codespaces.
2. Run:

```bash
# Install and verify the deterministic ModelGuard environment
source scripts/bootstrap_codespace.sh
python scripts/run_showcase.py
```

Expected terminal summary:

```text
ModelGuard showcase complete
F1: 0.771 -> 0.842
Diagnosis: feature_transformation (1.0)
Repair: validated | guard=True
Publish: GitHub=created DataHub=raised_and_resolved
Repeat: GitHub=noop DataHub=noop
```

The complete outputs are written to `artifacts/showcase/`.

## Option C — Local Python

Requirements:

- Python 3.11 or 3.12;
- Git; and
- no DataHub or GitHub credentials for fixture mode.

```bash
# Clone and verify the deterministic no-credential route
git clone https://github.com/buriro-ezekia/modelguard-datahub.git
cd modelguard-datahub
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
pytest
python scripts/run_showcase.py
```

## Option D — Complete live DataHub verification

This optional route creates a stable ML metadata graph, reads it through the SDK and the self-hosted MCP Server, verifies the model deployment link, and writes a resolved incident twice to demonstrate idempotency.

```bash
# Configure a local DataHub Core endpoint
export DATAHUB_GMS_URL="http://localhost:8080"
unset DATAHUB_GMS_TOKEN

# Install live dependencies and run the resilient complete verification
python -m pip install -e ".[dev,live]"
python scripts/run_live_datahub_complete.py \
  --install-mcp-server \
  --promote
```

When local GMS is offline, the wrapper starts `datahub docker quickstart --dump-logs-on-failure`, waits for readiness and then runs all SDK, MCP, ML lineage, deployment and incident checks. It never runs `datahub docker nuke`.

Required ending:

```text
LIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED
```

See `submission/LIVE_DATAHUB_EVIDENCE.md` for authenticated instances, managed MCP endpoints, output files and diagnostic details.

## What fixture mode proves

Fixture mode executes the real detection, diagnosis, repair, validation and publication logic against deterministic DataHub-shaped context and state files. It proves the complete failure-to-repair path, idempotency and safety without contacting external services.

## What live mode proves

Live mode proves actual DataHub connectivity, schema and lineage retrieval, MCP tool execution, ML-feature/model/deployment relationships and DataHub incident write-back. It is not required to use the hosted replay, but promoted evidence lets judges inspect the live outputs without operating a DataHub stack.

## Live integration boundaries

MCP verification uses read-only tools. MCP mutation tools remain disabled. The live DataHub incident operation is performed through the existing GraphQL writer only after the normal ModelGuard publication gates pass and the harness supplies explicit `--apply`.

## Troubleshooting

- `modelguard: command not found`: use `python -m modelguard` or rerun `source scripts/bootstrap_codespace.sh`.
- Port 8080 returns `Connection refused`: run the resilient wrapper shown in Option D; it starts a local quickstart when permitted.
- DataHub quickstart fails: inspect `artifacts/live_datahub_complete/datahub_quickstart.log`, `docker_ps.log`, `datahub_docker_check.log`, `inspect_*.log`, `logs_*.log` and `startup_diagnostics.json`.
- Expected evaluation exit code `1`: the demonstration intentionally begins with a failed F1 gate; the showcase script treats it as expected.
- `mcp-server-datahub` missing: install `.[live]` or use `--install-mcp-server`.
- MCP health route unavailable: inspect `artifacts/live_datahub_complete/mcp_server.log`.
- Live lineage initially empty: the harness retries while DataHub indexes newly emitted aspects.
- GitHub Pages returns 404: repository administrators must select **Settings → Pages → Source: GitHub Actions** once after merging the deployment workflow.
