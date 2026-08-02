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
# Update the live integration branch before rerunning the proof
git fetch origin
git switch feat/live-mcp-ml-evidence
git pull --ff-only origin feat/live-mcp-ml-evidence

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

The current MCP provider unwraps FastMCP `result` envelopes and preserves exact raw response URNs, so the model-to-deployment relationship can be verified even when the normalised response shape varies. The live incident writer waits for the resolved delivery marker to become queryable before it returns, ensuring the immediate repeated publication can return `noop` despite DataHub indexing delay.

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
- Expected evaluation exit code `1`: the demonstration intentionally begins with a failed F1 gate; the showcase script treats it as expected.
- Port 8080 returns `Connection refused`: run the resilient wrapper shown in Option D; it starts a local quickstart when permitted.
- MCP deployment check fails after context collection: pull the latest branch, then rerun Option D.
- Incident repeat is not `noop`: pull the latest branch, then rerun; the writer now confirms resolved-incident visibility before the first publication exits.
- DataHub quickstart fails: inspect `artifacts/live_datahub_complete/datahub_quickstart.log`, `docker_ps.log`, `datahub_docker_check.log`, `inspect_*.log`, `logs_*.log` and `startup_diagnostics.json`.
