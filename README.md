# ModelGuard: DataHub Production ML Agent

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated a repair, validated it, and handed the engineer a review-ready fix?

ModelGuard is an open-source, metadata-aware CI agent for machine-learning systems. It combines deterministic model evaluation, DataHub context, evidence-backed diagnosis and constrained repair validation so every decision remains inspectable.

## Project status

- **Phase 1 — complete:** deterministic metric-regression gate.
- **Phase 2 — complete:** provider-neutral DataHub entity, schema and lineage context collection through the Python SDK, MCP Server or deterministic fixtures.
- **Phase 3 — complete:** evidence extraction, competing root-cause hypotheses, transparent ranking and abstention.
- **Phase 4 — implemented:** constrained repair generation, static patch guardrails and isolated independent validation.
- **Phase 5 — next:** GitHub reporting and DataHub incident or resolution write-back.

Phase 4 does not merge or apply a patch to the source branch. A proposal is labelled `validated` only after static guardrails, targeted tests and the original metric policy all pass inside a temporary workspace.

## Implemented workflow

```text
Failed model evaluation
        ↓
Phase 1 deterministic regression gate
        ↓
Phase 2 DataHub ContextSnapshot
        ↓
Phase 3 evidence-backed diagnosis
        ↓
High-confidence supported hypothesis?
        ├── No  → abstain; no repair generated
        └── Yes
              ↓
AST-based minimal repair proposal
              ↓
Static patch guardrails
              ↓
Temporary isolated workspace
              ↓
Compile + targeted tests + model evaluation
              ↓
Metric restored within policy?
        ├── No  → validation failed; patch withheld
        └── Yes → validated diff and review report
```

## Safety model

ModelGuard separates diagnosis, generation and validation.

- Root-cause ranking does not authorise a code change.
- The Phase 4 MVP supports only the explicit `guarded_division` strategy.
- The leading hypothesis must be `feature_transformation`, high confidence and score at least `0.8`.
- The target file must be cited by changed-file evidence.
- The diagnosed denominator must be one of the affected fields.
- Only one allowed Python file may change.
- Protected areas such as `.github/`, `config/`, `scripts/` and `src/modelguard/` are denied.
- Oversized patches and unsafe tokens are rejected before execution.
- Validation commands run without a shell and only through an allow-listed Python executable.
- The patch is applied only to a temporary copy.
- The original workspace is hashed before and after validation.
- A patch is withheld unless tests pass and the Phase 1 metric gate is restored.
- ModelGuard never merges its own repair.

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

Exit status `1` means the adverse change exceeded the configured tolerance.

## Phase 2: collect DataHub context

The committed fixture is safe for CI and requires no credentials:

```bash
python -m modelguard context check --provider fixture

python -m modelguard context collect \
  --provider fixture \
  --lineage-direction both \
  --output artifacts/context_snapshot.json
```

The snapshot contains the model, schema, ownership, quality signals, three upstream lineage hops and one downstream deployment.

## Phase 3: diagnose the regression

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

Phase 3 exit statuses:

- `0`: evidence thresholds were met and hypotheses were ranked;
- `2`: input or configuration validation failed;
- `3`: ModelGuard abstained because evidence was insufficient or ambiguous.

## Phase 4: generate and validate a constrained repair

The committed demonstration workspace contains the diagnosed unsafe division. ModelGuard creates the proposal in memory and validates it only in an isolated copy:

```bash
python -m modelguard repair \
  --diagnosis artifacts/diagnosis_report.json \
  --evaluation examples/evaluation_failed.json \
  --case examples/repair_case.json \
  --workspace demo/broken_change \
  --plan-output artifacts/repair_plan.json \
  --validation-output artifacts/repair_validation.json \
  --patch-output artifacts/validated_patch.diff \
  --markdown-output artifacts/validated_repair_report.md
```

Expected verified result:

```text
Repair status: validated
Patch guard: approved
Source workspace unchanged: true
Pre-repair F1: 0.771
Post-repair F1: 0.842
Invalid transformed values: 0
```

Phase 4 exit statuses:

- `0`: the constrained repair passed guardrails, tests and metric validation;
- `2`: input, generation or validation configuration was invalid;
- `4`: the static patch guard rejected the proposal;
- `5`: isolated tests or the post-repair metric gate failed.

### Repair artefacts

- `repair_plan.json`: diagnosis link, strategy, hashes, exact replacement and unified diff.
- `repair_validation.json`: guardrail decisions, command results and post-repair metric gate.
- `validated_patch.diff`: emitted only when validation succeeds.
- `validated_repair_report.md`: review-ready explanation and safety statement.

The generated fix for the demonstration is intentionally minimal:

```python
if account_age_months <= 0:
    return 0.0
return total_spend / account_age_months
```

## Phase 3 ranking policy

| Signal | Maximum contribution |
|---|---:|
| Temporal proximity to the regression | 0.25 |
| Relevance to the DataHub lineage path | 0.25 |
| Ability to explain the failed metric | 0.20 |
| Quality or profile corroboration | 0.20 |
| Asset and field specificity | 0.10 |

Counter-evidence and low evidence diversity reduce the score. ModelGuard abstains when the top score is too low or the leading margin is too small.

## Connect through the DataHub Python SDK

```bash
pip install -e ".[datahub]"

export DATAHUB_GMS_URL="https://your-datahub.example.com"
export DATAHUB_GMS_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="sdk"

python -m modelguard context check --provider sdk
python -m modelguard context collect \
  --provider sdk \
  --urn "urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)" \
  --output artifacts/live_sdk_context.json
```

## Connect through the DataHub MCP Server

```bash
pip install -e ".[mcp]"

export DATAHUB_MCP_URL="https://your-tenant.acryl.io/integrations/ai/mcp/"
export DATAHUB_MCP_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="mcp"

python -m modelguard context check --provider mcp
python -m modelguard context collect \
  --provider mcp \
  --lineage-direction both \
  --output artifacts/live_mcp_context.json
```

For self-hosted DataHub, point `DATAHUB_MCP_URL` at the self-hosted MCP endpoint. Tokens are sent only through environment-configured authentication headers.

## Live integration test

Live verification is opt-in and skipped in ordinary CI:

```bash
export MODELGUARD_LIVE_DATAHUB=1
export MODELGUARD_DATAHUB_PROVIDER=sdk  # or mcp
pytest -m live_datahub
```

## Configuration

- `config/modelguard.yml`: non-secret DataHub settings.
- `config/thresholds.yml`: deterministic metric policies.
- `examples/regression_case.json`: changed files and deterministic observations.
- `examples/repair_case.json`: permitted repair target, strategy and validation commands.

Secrets, raw production rows and unrestricted repository access are not required by the deterministic demonstration.

## Roadmap

1. deterministic CI regression gate;
2. DataHub SDK and MCP context retrieval;
3. evidence-backed root-cause ranking;
4. constrained repair generation and independent validation;
5. GitHub reporting and DataHub incident or resolution write-back;
6. hosted demonstration and hackathon submission assets.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and secret-handling requirements.

## Licence

Licensed under the [Apache License 2.0](LICENSE).
