# ModelGuard: DataHub Production ML Agent

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated a repair, validated it, and handed the engineer a review-ready fix?

ModelGuard is an open-source, metadata-aware CI agent for machine-learning systems. It combines deterministic model evaluation, DataHub context and evidence-backed diagnosis so root-cause claims remain inspectable rather than becoming unsupported LLM guesses.

## Project status

- **Phase 1 — complete:** deterministic metric-regression gate.
- **Phase 2 — complete:** provider-neutral DataHub entity, schema and lineage context collection through the Python SDK, MCP Server or deterministic fixtures.
- **Phase 3 — complete:** evidence extraction, competing root-cause hypothesis generation, transparent ranking and abstention.
- **Phase 4 — next:** constrained repair generation and independent validation.

Phase 3 ranks hypotheses; it does not prove causality, generate a patch or authorise a repository change.

## Implemented workflow

```text
Failed model evaluation
        ↓
Phase 1 evaluation artefact
        ↓
Phase 2 DataHub ContextSnapshot
        ↓
Changed-file and runtime observations
        ↓
Evidence registry with stable IDs
        ↓
Competing root-cause hypotheses
        ↓
Deterministic scoring + counter-evidence penalties
        ↓
Ranked diagnosis or explicit abstention
        ↓
JSON and review-ready Markdown reports
```

## Phase 3 ranking policy

The ranker uses fixed, testable contributions:

| Signal | Maximum contribution |
|---|---:|
| Temporal proximity to the regression | 0.25 |
| Relevance to the DataHub lineage path | 0.25 |
| Ability to explain the failed metric | 0.20 |
| Quality or profile corroboration | 0.20 |
| Asset and field specificity | 0.10 |

Counter-evidence and low evidence diversity reduce the score. ModelGuard abstains when:

- the top score is below the minimum confidence threshold; or
- the margin between the first and second hypotheses is too small.

Every hypothesis contains supporting evidence IDs, counter-evidence IDs, score components, affected assets and fields, rationale and recommended checks.

## Codespaces quick start

```bash
source scripts/bootstrap_codespace.sh
```

Run the complete verification suite:

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
  --lineage-direction both \
  --output artifacts/context_snapshot.json
```

The snapshot contains the model, schema, ownership, quality signals, three upstream lineage hops and one downstream deployment.

## Phase 3: diagnose the regression

Run the complete deterministic demonstration:

```bash
python -m modelguard diagnose \
  --evaluation examples/evaluation_failed.json \
  --context artifacts/context_snapshot.json \
  --changes examples/regression_case.json \
  --output artifacts/diagnosis_report.json \
  --markdown-output artifacts/root_cause_report.md
```

Expected leading result:

```text
Category: feature_transformation
Confidence: high
Affected asset: analytics.customer_features
Affected fields: monthly_spend, account_age_months, total_spend
```

Exit statuses are:

- `0`: evidence thresholds were met and hypotheses were ranked;
- `2`: configuration, input or JSON validation failed;
- `3`: ModelGuard abstained because evidence was insufficient or ambiguous.

### Phase 3 input contract

The diagnosis command consumes:

1. a failed Phase 1 evaluation JSON object;
2. a Phase 2 `ContextSnapshot` JSON object;
3. a regression case containing changed files and deterministic observations.

The committed `examples/regression_case.json` records changed lines, symbols, fields, assets and baseline-versus-candidate observations. Secrets, raw production rows and unrestricted repository contents are not required.

### Phase 3 output contract

`diagnosis_report.json` includes:

- a deterministic diagnosis ID;
- ranking status and policy thresholds;
- a complete evidence registry;
- ranked competing hypotheses;
- supporting and counter-evidence references;
- component-level scores;
- an explicit top-hypothesis ID or `null` when ModelGuard abstains;
- warnings about fixture or incomplete evidence.

`root_cause_report.md` provides the same decision in a human-reviewable format and states that ranking does not prove causality.

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

For unattended CI/CD, use a scoped DataHub service-account token:

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

For self-hosted DataHub, point `DATAHUB_MCP_URL` at the self-hosted MCP endpoint. ModelGuard uses Streamable HTTP and sends the token only in the `Authorization` header.

## Configuration

`config/modelguard.yml` stores non-secret DataHub settings. `config/thresholds.yml` records deterministic metric policies. Phase 3 confidence and margin thresholds are CLI options so each CI policy remains explicit and visible.

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

## Security and reliability boundaries

- No token is stored in configuration, examples or logs.
- Phase 2 uses read-only DataHub operations.
- Fixture mode is the default, so forks and ordinary CI do not contact external systems.
- Every root-cause claim references collected evidence.
- Missing or ambiguous evidence causes abstention rather than a confident guess.
- Diagnosis and repair remain separate stages.
- ModelGuard does not merge its own changes.
- A future repair will be labelled validated only after independent deterministic checks pass.

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
