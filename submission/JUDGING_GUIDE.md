# ModelGuard Judging Guide

## The 30-second version

ModelGuard is a DataHub-grounded production ML agent. A pull-request change introduces invalid feature values and drops churn-model F1 from **0.842 to 0.771**. ModelGuard detects the regression, uses DataHub lineage and schema context to rank the changed transformation first, generates a two-line guard, validates it in an isolated workspace, restores F1 to **0.842**, posts one review-ready GitHub comment and records one resolved DataHub incident. Repeating publication creates no duplicates.

## Fastest evaluation path

1. Open the hosted demonstration: `https://buriro-ezekia.github.io/modelguard-datahub/`.
2. Select **Replay the incident** to watch all six phases.
3. Inspect `examples/` for the root-cause report, validated diff, validation receipt, GitHub comment and DataHub incident.
4. Run `python scripts/run_showcase.py` from a Codespace or local clone.

The one-command showcase uses deterministic fixtures and requires no credentials.

## Strongest live-integration path

A configured DataHub instance can run:

```bash
pip install -e ".[dev,live]"
export DATAHUB_GMS_URL="http://localhost:8080"
python scripts/run_live_datahub_evidence.py --promote
```

This creates a real ML graph, collects it through both the DataHub SDK and MCP Server, verifies the model deployment link, raises and resolves a live DataHub incident, and repeats publication to prove `noop` idempotency. Full instructions are in `submission/LIVE_DATAHUB_EVIDENCE.md`.

## What to inspect by judging criterion

### 1. Use of DataHub

- Provider-neutral context retrieval through the DataHub Python SDK, MCP Server or deterministic fixture.
- Entity, schema, ownership, quality-signal and bidirectional lineage collection.
- ML path represented from raw customers through features and training data to the model and deployment.
- Root-cause scores explicitly include lineage relevance and schema evidence.
- The resolved outcome is written back as an idempotent DataHub incident lifecycle record.
- Committed live SDK lineage evidence plus a reproducible complete SDK/MCP/ML/write-back harness.

Key files:

- `src/modelguard/context/datahub_sdk.py`
- `src/modelguard/context/datahub_mcp.py`
- `src/modelguard/context/normalise.py`
- `src/modelguard/reporting/datahub_writer.py`
- `scripts/load_live_ml_lineage.py`
- `scripts/run_live_datahub_evidence.py`
- `examples/live_datahub_context.json`
- `examples/datahub_incident.json`

### 2. Technical execution

- Deterministic metric policy and non-zero CI gate.
- Typed context, evidence, hypothesis, repair and publication contracts.
- Abstention for weak or ambiguous diagnosis.
- AST-based constrained repair generation.
- Protected-path, line-budget, file-type and unsafe-token guardrails.
- Temporary-workspace validation, no shell execution and source hash verification.
- Idempotent GitHub and DataHub publication.
- CI exercises the complete flow and verifies the second publication is `noop`.
- Official MCP nested lineage responses and SDK slot/property objects are normalised into the same stable contract.

### 3. Originality

ModelGuard does not stop at observability or emit an unsupported LLM suggestion. It combines deterministic detection, DataHub-grounded diagnosis, constrained code repair, independent metric validation and closed-loop metadata write-back.

### 4. Real-world usefulness

The target user is an ML platform or data platform team reviewing a change that silently degrades a production model. ModelGuard turns a failed metric into a reviewable, evidence-linked repair while retaining human control.

### 5. Submission quality

- Hosted interactive demonstration under `docs/`.
- One-command deterministic showcase.
- One-command live SDK/MCP/ML verification.
- Three prepared screenshots.
- Public Apache-2.0 repository.
- Sample outputs for every stage.
- Public demonstration video under three minutes.
- Explicit testing and safety instructions.

## Verified deterministic outcome

```text
Regression: f1_score 0.842 -> 0.771
Context: 3 upstream assets, 1 downstream deployment
Top cause: feature_transformation, score 1.0000, high confidence
Repair: 1 file, 2 added lines
Validation: 3 tests passed, invalid values 37 -> 0
Recovered F1: 0.842
GitHub first/repeat: created / noop
DataHub first/repeat: raised_and_resolved / noop
```

## Evidence labels

To avoid overstating the submission, ModelGuard separates three evidence levels:

1. **Deterministic verified showcase** — complete ML regression, diagnosis, repair, validation and fixture publication.
2. **Committed live SDK evidence** — actual DataHub Core connection and bidirectional dataset/data-job lineage.
3. **Complete live evidence** — promoted only after the SDK, MCP, ML lineage, deployment-link and live write-back harness reports every check as `true`.

## Safety boundary

The public hosted site is a read-only interactive replay of verified fixture artefacts. ModelGuard never applies or merges its own repair. MCP mutation tools are disabled in the live harness. Live GitHub and DataHub writes require explicit permission and scoped environment credentials where authentication is enabled.
