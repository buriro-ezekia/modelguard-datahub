# Live DataHub SDK, MCP and ML lineage verification

This procedure creates a real ML metadata graph in DataHub Core, reads it through both the DataHub Python SDK and the self-hosted DataHub MCP Server, and writes a resolved ModelGuard incident back to DataHub.

The public GitHub Pages demonstration remains a deterministic, read-only replay. This live verification is separate evidence that the provider and write-back integrations work against an actual DataHub deployment.

## What the verification proves

The harness performs the following operations:

1. creates three datasets with descriptions, ownership and schemas;
2. creates two data jobs connecting raw customer data to features and training data;
3. creates two ML features whose source is the training dataset;
4. creates a feature table, ML model group and `churn-model-v3`;
5. creates and links the `churn-api-prod` model deployment;
6. collects the live training-data and model context through the DataHub Python SDK;
7. starts the official self-hosted DataHub MCP Server over Streamable HTTP;
8. repeats context collection through the MCP tools `get_entities`, `list_schema_fields` and `get_lineage`;
9. raises and resolves a real DataHub incident, then repeats publication to verify `noop` idempotency; and
10. writes a machine-readable verification summary and, when requested, copies sanitised evidence to `examples/`.

## Prerequisites

- Python 3.11 or 3.12;
- a running DataHub Core or DataHub Cloud instance;
- `DATAHUB_GMS_URL` pointing to GMS;
- a service-account or personal token when the instance requires authentication; and
- enough permission to emit metadata and manage dataset incidents.

For the local DataHub quickstart:

```bash
# Configure ModelGuard for a local DataHub Core quickstart
export DATAHUB_GMS_URL="http://localhost:8080"
unset DATAHUB_GMS_TOKEN
```

For an authenticated environment:

```bash
# Configure ModelGuard for an authenticated DataHub environment
export DATAHUB_GMS_URL="https://your-datahub.example.com"
export DATAHUB_GMS_TOKEN="scoped-service-account-token"
```

Never commit a token. The generated evidence contains URNs, metadata and receipts but not credential values.

## Run the complete verification

Install the live integration dependencies once:

```bash
# Install the project, SDK, MCP client and pinned self-hosted MCP server
pip install -e ".[dev,live]"
```

Then run:

```bash
# Verify SDK, MCP, ML lineage, deployment linkage and DataHub write-back
python scripts/run_live_datahub_evidence.py --promote
```

When the MCP server executable is not already installed, the harness can install the pinned server package explicitly:

```bash
# Install the pinned MCP server only when it is missing, then run all checks
python scripts/run_live_datahub_evidence.py \
  --install-mcp-server \
  --promote
```

The local self-hosted server uses:

```text
MCP endpoint: http://127.0.0.1:8000/mcp
Health route: http://127.0.0.1:8000/health
Transport:    Streamable HTTP
Server:       mcp-server-datahub 0.6.0
```

A managed MCP endpoint can be used instead:

```bash
# Use an existing managed or separately hosted MCP endpoint
export DATAHUB_MCP_TOKEN="scoped-service-account-token"
python scripts/run_live_datahub_evidence.py \
  --external-mcp \
  --mcp-url "https://tenant.example.com/integrations/ai/mcp/" \
  --promote
```

## Required successful ending

```text
LIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED
```

The summary must report all checks as `true`, including:

```json
{
  "sdk_provider_verified": true,
  "mcp_provider_verified": true,
  "sdk_ml_lineage_verified": true,
  "mcp_ml_lineage_verified": true,
  "sdk_model_deployment_link_verified": true,
  "mcp_model_deployment_link_verified": true,
  "live_datahub_writeback_verified": true,
  "live_datahub_writeback_idempotent": true
}
```

## Generated evidence

The complete run writes to `artifacts/live_datahub_complete/`:

- `ml_lineage_manifest.json`;
- `sdk_training_context.json`;
- `mcp_training_context.json`;
- `sdk_model_context.json`;
- `mcp_model_context.json`;
- `datahub_writeback_first.json`;
- `datahub_writeback_repeat.json`;
- `complete_summary.json`; and
- diagnostic logs for loading, MCP startup and publication.

With `--promote`, successful JSON evidence is copied to `examples/live_datahub_*.json`. Review those files before committing them.

## Safety boundaries

The MCP verification uses read-only discovery and lineage tools. MCP mutation tools are not enabled. The only catalog write-back is ModelGuard's existing GraphQL incident lifecycle operation, which is protected by the normal publication gates and requires explicit `--apply` inside the harness.

The loader is idempotent: it replaces the same named metadata aspects for the same stable URNs rather than creating randomly named assets on every run.
