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

This optional route proves the same context contract against a real DataHub graph. It creates a stable ML path, reads it through the SDK and the self-hosted MCP Server, verifies the model deployment link, and writes a resolved incident twice to demonstrate idempotency.

Start DataHub first, then run:

```bash
# Configure a local DataHub Core quickstart
export DATAHUB_GMS_URL="http://localhost:8080"
unset DATAHUB_GMS_TOKEN

# Install the live dependencies and run all checks
pip install -e ".[dev,live]"
python scripts/run_live_datahub_evidence.py --promote
```

The equivalent command for an environment without the MCP server executable is:

```bash
# Install the pinned MCP server when it is missing
python scripts/run_live_datahub_evidence.py \
  --install-mcp-server \
  --promote
```

Required ending:

```text
LIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED
```

See `submission/LIVE_DATAHUB_EVIDENCE.md` for authenticated instances, managed MCP endpoints, output files and troubleshooting boundaries.

## What fixture mode proves

Fixture mode executes the real detection, diagnosis, repair, validation and publication logic against deterministic DataHub-shaped context and state files. It proves the complete failure-to-repair path, idempotency and safety without contacting external services.

## What live mode proves

Live mode proves actual DataHub connectivity, schema and lineage retrieval, MCP tool execution, ML-feature/model/deployment relationships and DataHub incident write-back. It is not required to use the hosted replay, but promoted evidence lets judges inspect the live outputs without operating a DataHub stack.

## Live integration boundaries

MCP verification uses read-only tools. MCP mutation tools remain disabled. The live DataHub incident operation is performed through the existing GraphQL writer only after the normal ModelGuard publication gates pass and the harness supplies explicit `--apply`.

## Troubleshooting

- `modelguard: command not found`: use `python -m modelguard` or rerun `source scripts/bootstrap_codespace.sh`.
- Expected evaluation exit code `1`: the demonstration intentionally begins with a failed F1 gate; the showcase script treats it as expected.
- `mcp-server-datahub` missing: install `.[live]` or use `--install-mcp-server`.
- MCP health route unavailable: inspect `artifacts/live_datahub_complete/mcp_server.log`.
- Live lineage initially empty: the harness retries while DataHub indexes newly emitted aspects.
- GitHub Pages returns 404: repository administrators must select **Settings → Pages → Source: GitHub Actions** once after merging the deployment workflow.
