# ModelGuard: DataHub Production ML Agent

[![ModelGuard CI](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/modelguard.yml/badge.svg)](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/modelguard.yml)
[![Deploy demo](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/pages.yml/badge.svg)](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/pages.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated the smallest supported repair, validated it independently and preserved the resolved incident in DataHub?

ModelGuard is an open-source, metadata-aware CI agent for production machine-learning systems. It combines deterministic model evaluation, DataHub context, evidence-backed diagnosis, constrained repair validation and idempotent outcome publication so every decision remains inspectable.

**Hosted demonstration:** <https://buriro-ezekia.github.io/modelguard-datahub/>  
**Judge in one command:** `python scripts/run_showcase.py`  
**Challenge category:** Production ML Agents

![ModelGuard hosted demo](docs/assets/screenshot-overview.svg)

## Verified result

The deterministic demonstration models a churn feature regression:

```text
F1 gate:               0.842 → 0.771 (failed)
DataHub context:       3 upstream assets, 1 downstream deployment
Leading diagnosis:     feature_transformation, score 1.0000, high confidence
Repair:                1 file, 2 added lines
Isolated validation:   3 targeted tests passed
Invalid values:        37 → 0
Recovered F1:          0.842
GitHub first/repeat:    created / noop
DataHub first/repeat:   raised_and_resolved / noop
```

## Six guarded phases

```text
Failed model evaluation
        ↓
1. Deterministic regression gate
        ↓
2. DataHub schema, ownership, quality and lineage context
        ↓
3. Evidence registry + competing root-cause hypotheses
        ↓
High-confidence supported diagnosis?
   ├── No  → abstain; no repair
   └── Yes
        ↓
4. Minimal constrained repair + static patch guard
        ↓
5. Temporary workspace + compile + tests + model evaluation
        ↓
Metric restored within policy?
   ├── No  → patch withheld
   └── Yes
        ↓
6. One idempotent GitHub comment + one resolved DataHub incident
```

### Phase 1 — Detect

`modelguard evaluate` compares an approved baseline with a candidate metric. A regression beyond the configured tolerance returns exit status `1` and emits stable JSON.

### Phase 2 — Context

`modelguard context collect` resolves entity metadata, schema, ownership, quality signals and bidirectional lineage through one of three providers:

- DataHub Python SDK;
- DataHub MCP Server over Streamable HTTP; or
- deterministic fixture mode for CI and public evaluation.

### Phase 3 — Diagnose

`modelguard diagnose` extracts evidence, generates competing hypotheses and ranks them using temporal proximity, lineage relevance, metric explanation, quality corroboration and field specificity. Counter-evidence reduces scores. Weak or ambiguous evidence causes explicit abstention.

### Phase 4 — Repair and validate

`modelguard repair` currently supports the explicit `guarded_division` strategy used by the demonstration. It applies strict path, file-count, line-budget, file-type and unsafe-token rules, then validates the patch only inside a temporary copy.

### Phase 5 — Publish

`modelguard publish` requires a ranked high-confidence diagnosis, approved patch guard, restored metric, matching repair identifiers and an unchanged source workspace. Publication is dry-run by default. Stable delivery markers prevent duplicate GitHub comments and DataHub incidents.

### Phase 6 — Showcase and submission

The repository includes:

- a responsive dependency-free GitHub Pages demonstration under `docs/`;
- a one-command end-to-end showcase;
- a judging guide and testing instructions;
- a complete Devpost description draft;
- an under-three-minute video script and shot list;
- desktop, evidence and mobile screenshots; and
- an automated submission-asset verifier.

## Quick start

### GitHub Codespaces

```bash
source scripts/bootstrap_codespace.sh
python scripts/run_showcase.py
```

### Local installation

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

The showcase needs no credentials and writes only to `artifacts/showcase/`.

## One-command showcase

```bash
python scripts/run_showcase.py
```

Expected final summary:

```text
ModelGuard showcase complete
F1: 0.771 -> 0.842
Diagnosis: feature_transformation (1.0)
Repair: validated | guard=True
Publish: GitHub=created DataHub=raised_and_resolved
Repeat: GitHub=noop DataHub=noop
```

The command executes the real CLI for all six phases and writes:

- `evaluation.json`;
- `context_snapshot.json`;
- `diagnosis_report.json` and `root_cause_report.md`;
- `repair_plan.json`, `repair_validation.json` and `validated_patch.diff`;
- `publication_receipt.json`, `github_pr_comment.md` and fixture states; and
- `showcase_summary.json`.

## The demonstrated repair

```diff
 def calculate_monthly_spend(
     total_spend: float,
     account_age_months: int,
 ) -> float:
+    if account_age_months <= 0:
+        return 0.0
     return total_spend / account_age_months
```

The proposal is applied only to an isolated copy. The source workspace is hashed before and after validation, and ModelGuard never applies or merges its own repair.

![Evidence-backed diagnosis and validated patch](docs/assets/screenshot-evidence.svg)

## DataHub integration

### Python SDK

```bash
pip install -e ".[datahub]"
export DATAHUB_GMS_URL="https://your-datahub.example.com"
export DATAHUB_GMS_TOKEN="scoped-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="sdk"
python -m modelguard context check --provider sdk
```

### MCP Server

```bash
pip install -e ".[mcp]"
export DATAHUB_MCP_URL="https://your-tenant.example.com/integrations/ai/mcp/"
export DATAHUB_MCP_TOKEN="scoped-service-account-token"
export MODELGUARD_DATAHUB_PROVIDER="mcp"
python -m modelguard context check --provider mcp
```

### Live incident write-back

```bash
export DATAHUB_GRAPHQL_URL="https://your-datahub.example.com/api/graphql"
export DATAHUB_GRAPHQL_TOKEN="scoped-incident-editor-token"

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

## Safety model

- Deterministic metric detection precedes reasoning.
- Root-cause ranking does not authorise code changes.
- Low-confidence or close-score diagnoses abstain.
- Only a cited file and approved repair strategy may be changed.
- `.github/`, `config/`, `scripts/` and `src/modelguard/` are protected from generated patches.
- Validation commands use `shell=False` and an allow-listed Python executable.
- Repairs are tested in a temporary workspace.
- The original workspace must remain hash-identical.
- The original metric policy must pass after repair.
- Publication is dry-run unless `--apply` is explicit.
- Credentials come only from environment variables and never enter receipts.
- Stable markers make GitHub and DataHub publication idempotent.
- ModelGuard never merges its own repair.

## Judge-facing assets

- [Judging guide](submission/JUDGING_GUIDE.md)
- [Testing instructions](submission/TESTING_INSTRUCTIONS.md)
- [Devpost draft](submission/DEVPOST_DRAFT.md)
- [Video script](submission/DEMO_SCRIPT.md)
- [Video shot list](submission/VIDEO_SHOT_LIST.md)
- [Release checklist](submission/RELEASE_CHECKLIST.md)
- [Sample outputs](examples/)

Verify the package:

```bash
python scripts/verify_submission.py
```

The verifier confirms all hosted-site references, visual assets and required submission sections. The only intentionally manual final field is the public video URL after recording and upload.

## Repository layout

```text
modelguard-datahub/
├── .github/workflows/       # CI and GitHub Pages deployment
├── config/                  # non-secret settings and thresholds
├── demo/                    # broken change and expected fix
├── docs/                    # hosted interactive demonstration
├── examples/                # verified outputs for every phase
├── scripts/                 # Codespaces bootstrap and showcase tools
├── src/modelguard/          # detection, context, diagnosis, repair, reporting
├── submission/              # judge, Devpost and video assets
└── tests/                   # unit, integration and regression coverage
```

## Project status

All six implementation phases are repository-complete and CI-verifiable. The hosted Pages deployment becomes public after the repository Pages source is set to **GitHub Actions**. The final hackathon action outside the repository is recording/uploading the public video and pasting its URL into the Devpost form.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and secret-handling requirements.

## License

Licensed under the [Apache License 2.0](LICENSE).
