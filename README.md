# ModelGuard: DataHub Production ML Agent

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated a repair, validated it, and handed the engineer a review-ready fix?

ModelGuard is an open-source, metadata-aware CI agent for machine-learning systems. It combines deterministic model evaluation, DataHub context, evidence-backed diagnosis, constrained repair validation and idempotent outcome publication so every decision remains inspectable.

## Project status

- **Phase 1 — complete:** deterministic metric-regression gate.
- **Phase 2 — complete:** provider-neutral DataHub entity, schema and lineage context collection through the Python SDK, MCP Server or deterministic fixtures.
- **Phase 3 — complete:** evidence extraction, competing root-cause hypotheses, transparent ranking and abstention.
- **Phase 4 — complete:** constrained repair generation, static patch guardrails and isolated independent validation.
- **Phase 5 — implemented:** review-ready GitHub reporting and DataHub incident lifecycle write-back.
- **Phase 6 — next:** hosted demonstration and hackathon submission assets.

ModelGuard never applies or merges its own repair. Publication is dry-run by default and external writes require explicit `--apply`.

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
Phase 4 minimal repair + static guardrails
              ↓
Temporary isolated workspace
              ↓
Compile + targeted tests + model evaluation
              ↓
Metric restored within policy?
        ├── No  → validation failed; patch withheld
        └── Yes
              ↓
Phase 5 validated-only publication gate
              ↓
One idempotent GitHub PR comment
              +
One resolved DataHub incident lifecycle record
```

## Safety model

ModelGuard separates diagnosis, generation, validation and publication.

- Root-cause ranking does not authorise a code change.
- The Phase 4 MVP supports only the explicit `guarded_division` strategy.
- The leading hypothesis must be `feature_transformation`, high confidence and score at least `0.8`.
- Only one cited Python file may change.
- Protected areas such as `.github/`, `config/`, `scripts/` and `src/modelguard/` are denied.
- Validation commands run without a shell through an allow-listed Python executable.
- The patch is applied only to a temporary copy.
- The original workspace is hashed before and after validation.
- A patch is withheld unless tests pass and the Phase 1 metric gate is restored.
- Publication requires a ranked high-confidence diagnosis, approved patch guard, restored metric, matching repair IDs and unchanged source workspace.
- Publication is dry-run unless `--apply` is supplied.
- Stable delivery markers prevent duplicate GitHub comments and DataHub incidents.
- Credentials are read only from environment variables and are never placed in receipts.
- ModelGuard never merges its own repair.

## Codespaces quick start

```bash
source scripts/bootstrap_codespace.sh
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

```bash
python -m modelguard context check --provider fixture

python -m modelguard context collect \
  --provider fixture \
  --lineage-direction both \
  --output artifacts/context_snapshot.json
```

The deterministic snapshot contains the model, schema, ownership, quality signals, three upstream lineage hops and one downstream deployment.

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

- `0`: hypotheses were ranked;
- `2`: input or configuration validation failed;
- `3`: ModelGuard abstained because evidence was insufficient or ambiguous.

## Phase 4: generate and validate a constrained repair

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

Expected result:

```text
Repair status: validated
Patch guard: approved
Source workspace unchanged: true
Pre-repair F1: 0.771
Post-repair F1: 0.842
Invalid transformed values: 0
```

Phase 4 exit statuses:

- `0`: repair passed guardrails, tests and metric validation;
- `2`: input, generation or validation configuration was invalid;
- `4`: static patch guard rejected the proposal;
- `5`: isolated tests or the post-repair metric gate failed.

## Phase 5: publish the validated outcome

### Safe fixture publication

Fixture mode creates deterministic local state files and does not contact external systems:

```bash
python -m modelguard publish \
  --diagnosis artifacts/diagnosis_report.json \
  --repair-plan artifacts/repair_plan.json \
  --validation artifacts/repair_validation.json \
  --patch artifacts/validated_patch.diff \
  --github-mode fixture \
  --datahub-mode fixture \
  --apply \
  --github-state artifacts/github_publication_state.json \
  --datahub-state artifacts/datahub_incident_state.json \
  --output artifacts/publication_receipt.json \
  --markdown-output artifacts/publication_report.md \
  --comment-output artifacts/github_pr_comment.md
```

The first execution should report:

```text
GitHub action: created
DataHub action: raised_and_resolved
Publication status: published
```

Running the same command again should report:

```text
GitHub action: noop
DataHub action: noop
```

Omit `--apply` to perform a dry run. Dry-run mode produces the plan and receipt but creates no fixture state and performs no live writes.

### Live GitHub publication

The authenticated token must be able to create and update pull-request issue comments:

```bash
export GITHUB_TOKEN="scoped-github-token"

python -m modelguard publish \
  --diagnosis artifacts/diagnosis_report.json \
  --repair-plan artifacts/repair_plan.json \
  --validation artifacts/repair_validation.json \
  --patch artifacts/validated_patch.diff \
  --github-mode live \
  --datahub-mode off \
  --apply \
  --output artifacts/github_publication_receipt.json
```

ModelGuard searches for its hidden delivery marker and creates, updates or leaves unchanged one PR comment.

### Live DataHub incident write-back

The current incident writer targets DataHub GraphQL and requires incident-edit privileges. The affected asset must be a Dataset URN.

```bash
export DATAHUB_GRAPHQL_URL="https://your-datahub.example.com/api/graphql"
export DATAHUB_GRAPHQL_TOKEN="scoped-datahub-token"

python -m modelguard publish \
  --diagnosis artifacts/diagnosis_report.json \
  --repair-plan artifacts/repair_plan.json \
  --validation artifacts/repair_validation.json \
  --patch artifacts/validated_patch.diff \
  --github-mode off \
  --datahub-mode live \
  --apply \
  --output artifacts/datahub_publication_receipt.json
```

`DATAHUB_GMS_URL` and `DATAHUB_GMS_TOKEN` are accepted as fallbacks. When only `DATAHUB_GMS_URL` is set, ModelGuard appends `/api/graphql`.

### Phase 5 artefacts

- `publication_receipt.json`: delivery plan and per-channel receipts.
- `publication_report.md`: human-readable publication evidence.
- `github_pr_comment.md`: exact review-ready comment body.
- `github_publication_state.json`: deterministic fixture comment state.
- `datahub_incident_state.json`: deterministic fixture incident state.

Phase 5 exit statuses:

- `0`: dry run completed or all enabled channels published/no-op successfully;
- `2`: input or safety validation failed;
- `6`: at least one enabled publication channel failed.

Verified examples are committed under `examples/`.

## Connect through the DataHub Python SDK

```bash
pip install -e ".[datahub]"

export DATAHUB_GMS_URL="https://your-datahub.example.com"
export DATAHUB_GMS_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="sdk"

python -m modelguard context check --provider sdk
```

## Connect through the DataHub MCP Server

```bash
pip install -e ".[mcp]"

export DATAHUB_MCP_URL="https://your-tenant.acryl.io/integrations/ai/mcp/"
export DATAHUB_MCP_TOKEN="your-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="mcp"

python -m modelguard context check --provider mcp
```

## Configuration

- `config/modelguard.yml`: non-secret DataHub retrieval settings.
- `config/thresholds.yml`: deterministic metric policies.
- `examples/regression_case.json`: changed files and deterministic observations.
- `examples/repair_case.json`: permitted repair target, strategy and validation commands.

Secrets, raw production rows and unrestricted repository access are not required by the deterministic demonstration.

## Roadmap

1. deterministic CI regression gate;
2. DataHub SDK and MCP context retrieval;
3. evidence-backed root-cause ranking;
4. constrained repair generation and independent validation;
5. GitHub reporting and DataHub incident lifecycle write-back;
6. hosted demonstration and hackathon submission assets.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and secret-handling requirements.

## Licence

Licensed under the [Apache License 2.0](LICENSE).
