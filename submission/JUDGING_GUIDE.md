# ModelGuard Judging Guide

## The 30-second version

ModelGuard is a DataHub-grounded production ML agent. A pull-request change introduces invalid feature values and drops churn-model F1 from **0.842 to 0.771**. ModelGuard detects the regression, uses DataHub lineage and schema context to rank the changed transformation first, generates a two-line guard, validates it in an isolated workspace, restores F1 to **0.842**, posts one review-ready GitHub comment and records one resolved DataHub incident. Repeating publication creates no duplicates.

## Fastest evaluation path

1. Open the hosted demonstration: `https://buriro-ezekia.github.io/modelguard-datahub/`.
2. Select **Replay the incident** to watch all six phases.
3. Inspect `examples/` for the root-cause report, validated diff, validation receipt, GitHub comment and DataHub incident.
4. Run `python scripts/run_showcase.py` from a Codespace or local clone.

The one-command showcase uses deterministic fixtures and requires no credentials.

## What to inspect by judging criterion

### 1. Use of DataHub

- Provider-neutral context retrieval through the DataHub Python SDK, MCP Server or deterministic fixture.
- Entity, schema, ownership, quality-signal and bidirectional lineage collection.
- ML path represented from raw customers through features and training data to the model and deployment.
- Root-cause scores explicitly include lineage relevance and schema evidence.
- The resolved outcome is written back as an idempotent DataHub incident lifecycle record.

Key files:

- `src/modelguard/context/datahub_sdk.py`
- `src/modelguard/context/datahub_mcp.py`
- `src/modelguard/reporting/datahub_writer.py`
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

### 3. Originality

ModelGuard does not stop at observability or emit an unsupported LLM suggestion. It combines deterministic detection, DataHub-grounded diagnosis, constrained code repair, independent metric validation and closed-loop metadata write-back.

### 4. Real-world usefulness

The target user is an ML platform or data platform team reviewing a change that silently degrades a production model. ModelGuard turns a failed metric into a reviewable, evidence-linked repair while retaining human control.

### 5. Submission quality

- Hosted interactive demonstration under `docs/`.
- One-command showcase.
- Three prepared screenshots.
- Public Apache-2.0 repository.
- Sample outputs for every stage.
- Under-three-minute video script and shot list.
- Explicit testing and safety instructions.

## Verified demonstration outcome

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

## Safety boundary

The public hosted site is a read-only interactive replay of verified fixture artefacts. ModelGuard never applies or merges its own repair. Live GitHub and DataHub writes require explicit `--apply` and scoped environment credentials.
