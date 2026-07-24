# ModelGuard: DataHub Production ML Agent

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated a repair, validated it, and handed the engineer a review-ready fix?

ModelGuard is an open-source, metadata-aware CI agent for machine-learning systems. It combines deterministic model evaluation with DataHub context so later diagnosis stages can reason from verified schemas, ownership, quality signals and lineage rather than guesswork.

## Project status

- **Phase 1 — complete:** deterministic metric-regression gate.
- **Phase 2 — complete:** provider-neutral DataHub entity, schema and lineage context collection through the Python SDK, MCP Server or deterministic fixtures.
- **Phase 3 — next:** evidence-backed root-cause hypothesis generation and ranking.

Phase 2 is deliberately read-only. It does not generate repairs, post GitHub comments or write incidents back to DataHub.

## Phase 2 architecture

```text
CLI / future CI orchestrator
          ↓
ContextCollector
          ↓
 ┌────────┼──────────────┐
 │        │              │
Fixture   DataHub SDK    DataHub MCP
provider  provider       provider
 │        │              │
 └────────┴──────────────┘
          ↓
Provider-neutral ContextSnapshot
(entity + schema + owners + quality signals + lineage)
```

The MCP provider calls the read-only `get_entities`, `list_schema_fields` and `get_lineage` tools. The SDK provider calls `DataHubClient.entities.get()` and `DataHubClient.lineage.get_lineage()`.

## Codespaces quick start

```bash
source scripts/bootstrap_codespace.sh
```

Run the complete local verification suite:

```bash
ruff check .
pytest
```

## Phase 1: evaluate a metric

```bash
python -m modelguard evaluate \
  --metric f1_score \
  --baseline 0.842 \
  --candidate 0.771 \
  --max-regression 0.02 \
  --output artifacts/evaluation.json
```

Exit status `1` means the configured regression threshold was exceeded.

## Phase 2: collect context without credentials

The committed fixture models the churn-model demonstration lineage and is safe for CI:

```bash
python -m modelguard context check --provider fixture

python -m modelguard context collect \
  --provider fixture \
  --output artifacts/context_snapshot.json
```

The generated snapshot contains the model, schema fields, ownership, quality signals, three upstream lineage hops and one downstream deployment. A representative output is committed at `examples/context_snapshot.json`.

## Connect through the DataHub Python SDK

Install the SDK integration:

```bash
pip install -e ".[datahub]"
```

Set credentials through the environment, never in YAML:

```bash
export DATAHUB_GMS_URL="https://your-datahub.example.com"
export DATAHUB_GMS_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="sdk"
```

Verify and collect:

```bash
python -m modelguard context check --provider sdk

python -m modelguard context collect \
  --provider sdk \
  --urn "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)" \
  --output artifacts/live_sdk_context.json
```

## Connect through the DataHub MCP Server

Install the MCP integration:

```bash
pip install -e ".[mcp]"
```

For an unattended CI/CD workflow, use a scoped DataHub service-account token:

```bash
export DATAHUB_MCP_URL="https://your-tenant.acryl.io/integrations/ai/mcp/"
export DATAHUB_MCP_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="mcp"
```

Verify and collect:

```bash
python -m modelguard context check --provider mcp

python -m modelguard context collect \
  --provider mcp \
  --lineage-direction both \
  --output artifacts/live_mcp_context.json
```

For self-hosted DataHub, point `DATAHUB_MCP_URL` at the self-hosted MCP endpoint. ModelGuard uses Streamable HTTP and places the token only in the `Authorization` header.

## Configuration

`config/modelguard.yml` stores non-secret settings only:

- context provider;
- model URN;
- maximum lineage hops;
- result and schema limits;
- names of environment variables that hold tokens.

`config/thresholds.yml` records the initial deterministic metric policies.

Environment variables override connection settings:

| Variable | Purpose |
|---|---|
| `MODELGUARD_DATAHUB_PROVIDER` | Select `fixture`, `sdk` or `mcp` |
| `DATAHUB_GMS_URL` | DataHub GMS URL for the SDK |
| `DATAHUB_GMS_TOKEN` | SDK service-account token |
| `DATAHUB_MCP_URL` | DataHub MCP Streamable HTTP endpoint |
| `DATAHUB_MCP_TOKEN` | MCP service-account token |

## Live integration test

Live verification is opt-in and skipped in ordinary CI:

```bash
export MODELGUARD_LIVE_DATAHUB=1
export MODELGUARD_DATAHUB_PROVIDER=sdk  # or mcp
pytest -m live_datahub
```

## Security boundaries

- No token is stored in configuration, examples or logs.
- Phase 2 uses read-only DataHub operations.
- Fixture mode is the default, so forks and CI do not contact external systems.
- Live tests require an explicit opt-in environment variable.
- Retrieval failures return a non-zero command status rather than a partial-success claim.
- Collected context is normalised into a provider-neutral JSON contract before later agent reasoning.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and secret-handling requirements.

## Roadmap

1. deterministic CI regression gate;
2. DataHub SDK and MCP context retrieval;
3. evidence-backed root-cause ranking;
4. constrained repair generation and independent validation;
5. GitHub reporting and DataHub incident or resolution write-back;
6. hosted demonstration and hackathon submission assets.

## Licence

Licensed under the [Apache License 2.0](LICENSE).
