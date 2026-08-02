# ModelGuard: DataHub Production ML Agent

[![ModelGuard CI](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/modelguard.yml/badge.svg)](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/modelguard.yml)
[![Deploy demo](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/pages.yml/badge.svg)](https://github.com/buriro-ezekia/modelguard-datahub/actions/workflows/pages.yml)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)

> What if a CI/CD pipeline did not merely detect an ML regression, but traced the likely cause through DataHub, proposed the smallest defensible repair, validated it independently and returned a review-ready result?

ModelGuard is a metadata-aware production ML agent built for the **Production ML Agents** challenge. It turns a failed model-quality gate into an evidence-backed investigation, a constrained repair proposal and a durable operational record.

DataHub provides the connected context: datasets, schemas, ownership, quality signals, jobs, features, models, deployments and lineage. ModelGuard then applies deterministic policy gates to decide whether it may diagnose, repair, validate or publish.

**ModelGuard never merges its own repair.** It keeps the final decision with an engineer.

## Project status

The complete demonstrated flow is implemented and verified.

- The public showcase is deterministic and requires no credentials.
- The DataHub Python SDK integration has been verified against a live DataHub Core instance.
- The official self-hosted DataHub MCP Server has been verified over Streamable HTTP.
- Upstream and downstream ML lineage has been retrieved through both SDK and MCP providers.
- The exact model-to-deployment relationship has been verified through live SDK model metadata.
- Live DataHub incident write-back and idempotency have been verified.
- Sanitised live evidence is committed under [`examples/`](examples/).

## Judge-facing links

| Resource | Link |
|---|---|
| Interactive demonstration | [Open the hosted demo](https://buriro-ezekia.github.io/modelguard-datahub/) |
| Demonstration video | [Watch the 2 minute 34 second video](https://youtu.be/S96pbK7k_nc) |
| Generated evidence | [Inspect `examples/`](examples/) |
| Fast judging guide | [Read the judging guide](submission/JUDGING_GUIDE.md) |
| Reproduction instructions | [Read the testing instructions](submission/TESTING_INSTRUCTIONS.md) |
| Live DataHub verification | [Read the live verification guide](submission/LIVE_DATAHUB_EVIDENCE.md) |

![ModelGuard hosted demonstration](docs/assets/screenshot-overview.svg)

## The problem

A production model can deteriorate because of a change that looks ordinary in code review: a removed boundary check, an altered schema, a null-handling mistake or a feature transformation that fails at the edge of its valid range.

A conventional CI pipeline can report that a metric fell. It usually cannot answer the questions that matter next:

- Which upstream asset is relevant?
- What changed near the failure?
- Which explanation best fits the metric and data evidence?
- Can the smallest safe correction be tested without changing the source workspace?
- Can the resolved result be preserved for the next engineer or agent?

ModelGuard closes that gap by combining deterministic ML gates with DataHub metadata and lineage.

## Six guarded phases

```text
Failed model evaluation
        ↓
1. Detect: deterministic regression gate
        ↓
2. Context: DataHub metadata and lineage
        ↓
3. Diagnose: evidence registry and competing hypotheses
        ↓
High-confidence supported diagnosis?
   ├── No  → abstain; no repair
   └── Yes
        ↓
4. Repair: minimal constrained patch
        ↓
5. Validate: temporary workspace, tests and metric re-evaluation
        ↓
Metric restored within policy?
   ├── No  → withhold the patch
   └── Yes
        ↓
6. Publish: review output and resolved DataHub incident
```

### 1. Detect

`modelguard evaluate` compares the candidate metric with an approved baseline. A regression beyond the configured tolerance returns exit status `1` and emits stable JSON. Agent reasoning cannot override the numerical gate.

### 2. Collect DataHub context

`modelguard context collect` resolves entity metadata, schema, ownership, quality signals and bidirectional lineage through one of three providers:

- DataHub Python SDK;
- DataHub MCP Server over Streamable HTTP; or
- deterministic fixture mode for public evaluation and CI.

### 3. Diagnose

`modelguard diagnose` extracts evidence, generates competing hypotheses and ranks them using temporal proximity, lineage relevance, metric explanation, quality corroboration and field specificity. Counter-evidence lowers unsupported explanations. Weak or ambiguous evidence causes explicit abstention.

### 4. Propose a constrained repair

`modelguard repair` supports the explicit `guarded_division` strategy used in the demonstration. It enforces path, file-count, line-budget, file-type and unsafe-token rules before a patch may proceed.

### 5. Validate independently

The patch is applied only inside a temporary copy. ModelGuard compiles the code, runs allow-listed tests and repeats the original metric evaluation. The source workspace is hashed before and after validation and must remain unchanged.

### 6. Publish once

`modelguard publish` requires a high-confidence diagnosis, an approved patch guard, a restored metric, matching repair identifiers and an unchanged source workspace. Publication is a dry run unless `--apply` is explicit. Stable delivery markers prevent duplicate GitHub comments and DataHub incidents.

## Verified deterministic showcase

The public showcase models a churn feature regression caused by direct division in a feature transformation.

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

The hosted site is a read-only replay of generated fixture artefacts. The same expected result is checked in GitHub Actions.

### Run the showcase

```bash
# Run the complete deterministic six-phase workflow
python scripts/run_showcase.py
```

Expected ending:

```text
ModelGuard showcase complete
F1: 0.771 -> 0.842
Diagnosis: feature_transformation (1.0)
Repair: validated | guard=True
Publish: GitHub=created DataHub=raised_and_resolved
Repeat: GitHub=noop DataHub=noop
```

## Demonstrated repair

```diff
 def calculate_monthly_spend(
     total_spend: float,
     account_age_months: int,
 ) -> float:
+    if account_age_months <= 0:
+        return 0.0
     return total_spend / account_age_months
```

The proposal changes two lines in one cited function. ModelGuard validates it in isolation and never applies or merges it into the source repository.

![Evidence-backed diagnosis and validated patch](docs/assets/screenshot-evidence.svg)

## Verified live DataHub integration

The live harness creates a stable ML metadata graph covering:

```text
raw customer dataset
        ↓
feature-engineering data job
        ↓
feature dataset
        ↓
training data job
        ↓
training dataset
        ↓
ML features and feature table
        ↓
churn-model-v3
        ↓
churn-api-prod
```

It then verifies the graph through the DataHub SDK and the self-hosted MCP Server, followed by live DataHub incident publication.

The committed summary reports all supported checks as passed:

```json
{
  "sdk_provider_verified": true,
  "mcp_provider_verified": true,
  "sdk_ml_lineage_verified": true,
  "mcp_ml_lineage_verified": true,
  "mcp_model_context_verified": true,
  "sdk_model_deployment_link_verified": true,
  "datahub_model_deployment_link_verified": true,
  "live_datahub_writeback_verified": true,
  "live_datahub_writeback_idempotent": true
}
```

The tested MCP context contained four upstream assets and five downstream assets for the training dataset. The final committed write-back evidence reused the existing resolved incident and returned `noop` for both publication attempts, demonstrating stable idempotency rather than creating a duplicate.

### Important MCP capability boundary

The tested combination was DataHub Core 1.5 with `mcp-server-datahub` 0.6.0.

MCP verified:

- server connectivity;
- training-data context;
- model context; and
- upstream and downstream ML lineage.

The model-to-deployment association is stored as the named `MLModelProperties.deployments` relationship. That relationship was not exposed by the tested MCP `get_lineage` response, so ModelGuard does not claim that it was. The exact deployment URN was verified through live SDK model metadata from the same DataHub graph.

This distinction is recorded in [`examples/live_datahub_complete_summary.json`](examples/live_datahub_complete_summary.json) and [`examples/live_datahub_model_deployment_relationship.json`](examples/live_datahub_model_deployment_relationship.json).

### Run the live verification

Requirements:

- Python 3.11 or 3.12;
- Docker and Docker Compose v2 for a local DataHub quickstart; and
- permission to emit metadata and manage incidents.

```bash
# Install ModelGuard with live DataHub and MCP dependencies
python -m pip install -e ".[dev,live]"

# Use a local DataHub Core instance
export DATAHUB_GMS_URL="http://localhost:8080"
unset DATAHUB_GMS_TOKEN

# Start DataHub when necessary and verify all supported live capabilities
python scripts/run_live_datahub_verified.py \
  --install-mcp-server \
  --promote
```

Required ending:

```text
LIVE DATAHUB SDK, MCP, ML LINEAGE AND WRITE-BACK PASSED
```

The harness never runs `datahub docker nuke`. See [`submission/LIVE_DATAHUB_EVIDENCE.md`](submission/LIVE_DATAHUB_EVIDENCE.md) for authenticated environments, managed MCP endpoints, generated artefacts and safety notes.

## Installation

### GitHub Codespaces

```bash
# Install the development environment and run the deterministic showcase
source scripts/bootstrap_codespace.sh
python scripts/run_showcase.py
```

### Local Python

```bash
# Clone, create an environment and verify the project
 git clone https://github.com/buriro-ezekia/modelguard-datahub.git
 cd modelguard-datahub
 python -m venv .venv
 source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
 python -m pip install --upgrade pip
 python -m pip install -e ".[dev]"
 ruff check .
 pytest
 python scripts/run_showcase.py
```

The deterministic showcase requires no credentials and writes only generated output under `artifacts/`.

## Safety boundaries

- Deterministic metric detection precedes diagnosis.
- Root-cause ranking does not authorise a code change.
- Low-confidence or closely ranked diagnoses abstain.
- Only a cited file and approved repair strategy may be changed.
- `.github/`, `config/`, `scripts/` and `src/modelguard/` are protected from generated patches.
- Validation commands use `shell=False` and an allow-listed Python executable.
- Repairs are tested in a temporary workspace.
- The original workspace must remain hash-identical.
- The original metric policy must pass after repair.
- Publication remains a dry run unless `--apply` is supplied.
- Credentials come from environment variables and never enter receipts.
- MCP mutation tools remain disabled in the live verification.
- Stable markers make GitHub and DataHub publication idempotent.
- ModelGuard never merges its own repair.

## Evidence

The [`examples/`](examples/) directory contains generated evidence for the deterministic showcase and the live DataHub verification.

Key live files include:

- [`live_datahub_complete_summary.json`](examples/live_datahub_complete_summary.json);
- [`live_datahub_ml_lineage_manifest.json`](examples/live_datahub_ml_lineage_manifest.json);
- [`live_datahub_sdk_ml_context.json`](examples/live_datahub_sdk_ml_context.json);
- [`live_datahub_mcp_ml_context.json`](examples/live_datahub_mcp_ml_context.json);
- [`live_datahub_sdk_model_context.json`](examples/live_datahub_sdk_model_context.json);
- [`live_datahub_mcp_model_context.json`](examples/live_datahub_mcp_model_context.json);
- [`live_datahub_model_deployment_relationship.json`](examples/live_datahub_model_deployment_relationship.json); and
- the first and repeat write-back receipts.

Generated runtime output remains under `artifacts/` and is intentionally ignored by Git. Only reviewed, sanitised evidence is promoted to `examples/`.

Run the repository verifier with:

```bash
# Check the complete submission package
python scripts/verify_submission.py
```

## Current scope and honest limitations

ModelGuard is a focused hackathon implementation rather than a general autonomous coding system.

- The current repair catalogue contains one explicit strategy: `guarded_division`.
- The public website is an interactive replay, not a browser-based live DataHub client.
- The deterministic evidence extractor and hypothesis ranking do not require an external model API.
- The tested MCP version did not expose `MLModelProperties.deployments` through `get_lineage`; the exact relationship was verified through the SDK instead.
- Live GitHub and DataHub writes require explicit permission and scoped credentials where authentication is enabled.
- ModelGuard proposes and validates repairs but does not approve or merge them.

These limits are deliberate. They keep the demonstrated claims reproducible and the repair authority narrower than the diagnostic context.

## Repository layout

```text
modelguard-datahub/
├── .github/workflows/       # CI and GitHub Pages deployment
├── config/                  # non-secret policies and thresholds
├── demo/                    # regression scenario and expected repair
├── docs/                    # hosted interactive demonstration
├── examples/                # reviewed deterministic and live evidence
├── scripts/                 # bootstrap, showcase and live verification
├── src/modelguard/          # detection, context, diagnosis, repair and reporting
├── submission/              # judging, testing and live evidence guides
└── tests/                   # unit, integration and regression coverage
```

## Licence

ModelGuard is released under the Apache License 2.0. See [`LICENSE`](LICENSE).
