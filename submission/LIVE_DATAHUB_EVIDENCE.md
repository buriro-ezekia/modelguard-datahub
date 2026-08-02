# Live DataHub SDK, MCP and ML context verification

This procedure creates a real ML metadata graph in DataHub Core, reads it through the DataHub Python SDK and the self-hosted DataHub MCP Server, and writes a resolved ModelGuard incident back to DataHub.

The public GitHub Pages demonstration remains a deterministic, read-only replay. This live verification is separate evidence that the provider and write-back integrations work against an actual DataHub deployment.

## What the verification proves

The harness:

1. confirms that the configured DataHub GMS endpoint is reachable;
2. starts a local DataHub quickstart automatically when `localhost:8080` is offline;
3. creates datasets, data jobs, ML features, a feature table, an ML model group, `churn-model-v3`, and the `churn-api-prod` deployment;
4. collects live training-data and model context through the DataHub Python SDK;
5. starts the official self-hosted DataHub MCP Server over Streamable HTTP;
6. repeats training-data and model collection through `get_entities`, `list_schema_fields`, and `get_lineage`;
7. verifies upstream and downstream ML lineage through both SDK and MCP;
8. verifies the exact model-to-deployment relationship from `MLModelProperties.deployments` through the SDK;
9. raises and resolves a real DataHub incident and repeats publication to verify `noop` idempotency; and
10. writes machine-readable evidence and optionally promotes sanitised JSON to `examples/`.

## Important capability boundary

DataHub MCP Server `get_lineage` exposes lineage edges. The model-to-deployment association used here is a named metadata relationship stored in `MLModelProperties.deployments`; it was not exposed in the MCP Server 0.6.0 response produced by DataHub Core 1.5.

The final verifier therefore does not make the unsupported claim that MCP returned the deployment relationship. It proves:

- live MCP connectivity;
- MCP retrieval of the intended training dataset and ML model;
- MCP upstream and downstream ML lineage;
- the exact deployment relationship through live SDK model metadata from the same DataHub graph; and
- live, idempotent DataHub incident write-back.

A failure in any supported check remains fatal. Only the unsupported MCP deployment-relationship assertion is reclassified, and only when every other live check passes.

## Prerequisites

- Python 3.11 or 3.12;
- Docker and Docker Compose v2 for a local quickstart;
- `DATAHUB_GMS_URL` pointing to GMS;
- a service-account or personal token when authentication is enabled; and
- permission to emit metadata and manage incidents.

For a local quickstart:

```bash
# Configure ModelGuard for local DataHub Core
export DATAHUB_GMS_URL="http://localhost:8080"
unset DATAHUB_GMS_TOKEN
```

Never commit a token. Generated evidence contains URNs, metadata and receipts, but not credential values.

## Install dependencies

```bash
# Install ModelGuard, the DataHub SDK, MCP client and pinned MCP server
python -m pip install -e ".[dev,live]"
```

## Definitive live command

```bash
# Start DataHub when necessary and verify all supported live capabilities
python scripts/run_live_datahub_verified.py \
  --install-mcp-server \
  --promote
```

To prohibit automatic quickstart startup:

```bash
# Require an already-running DataHub instance
python scripts/run_live_datahub_verified.py \
  --no-start-datahub \
  --install-mcp-server \
  --promote
```

The harness never runs `datahub docker nuke`.

## Required successful ending

```text
LIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED
```

The final summary must report:

```json
{
  "sdk_provider_verified": true,
  "mcp_provider_verified": true,
  "sdk_ml_lineage_verified": true,
  "mcp_ml_lineage_verified": true,
  "mcp_model_context_verified": true,
  "datahub_model_deployment_link_verified": true,
  "live_datahub_writeback_verified": true,
  "live_datahub_writeback_idempotent": true
}
```

The summary also contains `mcp_capability_scope.not_claimed`, which records that MCP exposure of `MLModelProperties.deployments` is not claimed for this tested version combination.

## Generated evidence

The run writes to `artifacts/live_datahub_complete/`:

- `ml_lineage_manifest.json`;
- `sdk_training_context.json`;
- `mcp_training_context.json`;
- `sdk_model_context.json`;
- `mcp_model_context.json`;
- `model_deployment_relationship.json`;
- `datahub_writeback_first.json`;
- `datahub_writeback_repeat.json`;
- `complete_summary.json`; and
- diagnostic logs for startup, loading, MCP and publication.

With `--promote`, successful JSON evidence is copied to `examples/live_datahub_*.json`. Review those files before committing them.

## Safety boundaries

MCP verification uses read-only discovery and lineage tools. MCP mutation tools remain disabled. The only catalog write-back is ModelGuard's existing incident lifecycle operation, protected by normal publication gates and explicit apply behaviour inside the harness.

The loader is idempotent: it replaces named metadata aspects for stable URNs instead of creating randomly named assets on every run.
