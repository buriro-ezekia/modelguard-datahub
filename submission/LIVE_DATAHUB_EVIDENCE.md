# Live DataHub SDK, MCP and ML lineage verification

This procedure creates a real ML metadata graph in DataHub Core, reads it through both the DataHub Python SDK and the self-hosted DataHub MCP Server, and writes a resolved ModelGuard incident back to DataHub.

The public GitHub Pages demonstration remains a deterministic, read-only replay. This live verification is separate evidence that the provider and write-back integrations work against an actual DataHub deployment.

## What the verification proves

The harness performs the following operations:

1. confirms that the configured DataHub GMS endpoint is reachable;
2. starts a local DataHub quickstart automatically when `localhost:8080` is offline;
3. creates three datasets with descriptions, ownership and schemas;
4. creates two data jobs connecting raw customer data to features and training data;
5. creates two ML features whose source is the training dataset;
6. creates a feature table, ML model group and `churn-model-v3`;
7. creates and links the `churn-api-prod` model deployment;
8. collects the live training-data and model context through the DataHub Python SDK;
9. starts the official self-hosted DataHub MCP Server over Streamable HTTP;
10. repeats context collection through the MCP tools `get_entities`, `list_schema_fields` and `get_lineage`;
11. raises and resolves a real DataHub incident, then repeats publication to verify `noop` idempotency; and
12. writes a machine-readable verification summary and, when requested, copies sanitised evidence to `examples/`.

The MCP provider preserves exact URNs from both normalised records and raw tool responses. It also unwraps FastMCP `result` envelopes and JSON-encoded structured content before normalisation. This ensures that an ML model deployment link remains verifiable even when the server response shape differs from a plain dictionary.

The live DataHub writer applies an eventual-consistency barrier after resolving an incident. It waits until the resolved incident and its stable ModelGuard delivery marker are queryable before returning success, allowing the immediate repeat publication to return `noop` reliably instead of creating a duplicate.

## Prerequisites

- Python 3.11 or 3.12;
- Docker and Docker Compose v2 for a local DataHub quickstart;
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

## Install the live dependencies

```bash
# Install the project, DataHub SDK, MCP client and pinned self-hosted MCP server
python -m pip install -e ".[dev,live]"
```

## Recommended one-command verification

Use the resilient wrapper. It first checks `/health` and `/config`. When the configured endpoint is local and offline, it runs `datahub docker quickstart --dump-logs-on-failure`, waits for GMS and then launches the complete evidence harness.

```bash
# Start local DataHub when necessary, then verify SDK, MCP, ML lineage and write-back
python scripts/run_live_datahub_complete.py \
  --install-mcp-server \
  --promote
```

The wrapper never runs `datahub docker nuke`. Existing DataHub data is therefore not deleted automatically.

To require an already-running DataHub instance and prohibit automatic quickstart startup:

```bash
# Fail rather than starting DataHub when GMS is offline
python scripts/run_live_datahub_complete.py \
  --no-start-datahub \
  --install-mcp-server \
  --promote
```

An optional quickstart version can be selected explicitly:

```bash
# Start the latest stable DataHub quickstart before verification
python scripts/run_live_datahub_complete.py \
  --datahub-version stable \
  --install-mcp-server \
  --promote
```

## Lower-level evidence command

When DataHub GMS is already healthy, the underlying evidence command can still be run directly:

```bash
# Run the evidence stages without managing DataHub startup
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
python scripts/run_live_datahub_complete.py \
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

## Startup diagnostics

When local DataHub cannot start or the final evidence run fails, the wrapper captures evidence rather than returning only a connection-refused message. Diagnostic files can include:

- `datahub_quickstart.log`;
- `datahub_docker_check.log`;
- `docker_info.log`;
- `docker_ps.log`;
- `docker_stats.log`;
- `inspect_*.log`;
- `logs_*.log`; and
- `startup_diagnostics.json`.

The inspection records include container image, running state, exit code, OOM flag and health status. This distinguishes an unavailable GMS endpoint from OpenSearch startup failure, system-update failure, port conflicts and memory exhaustion.

## Safety boundaries

The MCP verification uses read-only discovery and lineage tools. MCP mutation tools are not enabled. The only catalog write-back is ModelGuard's existing GraphQL incident lifecycle operation, which is protected by the normal publication gates and requires explicit `--apply` inside the harness.

The loader is idempotent: it replaces the same named metadata aspects for the same stable URNs rather than creating randomly named assets on every run.

## Troubleshooting

- MCP context succeeds but the deployment check fails: pull the latest branch so structured MCP `result` envelopes are unwrapped and raw deployment URNs are retained in `provider_metadata`.
- The first incident write succeeds but the repeat is not `noop`: pull the latest branch so the writer waits for the resolved delivery marker to become queryable before returning.
- The local MCP server does not start: inspect `mcp_server.log` and confirm that `mcp-server-datahub==0.6.0` is installed.
- DataHub quickstart fails: inspect the startup diagnostics listed above; the wrapper does not delete existing volumes.
