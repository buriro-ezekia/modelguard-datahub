# ModelGuard: DataHub Production ML Agent

> What if your CI/CD pipeline did not merely catch a model regression, but traced the cause, generated a repair, validated it, and handed the engineer a review-ready fix?

ModelGuard is an open-source, metadata-aware CI agent for machine-learning systems. The planned application will use DataHub lineage, schemas, ownership and quality context to diagnose upstream causes of model regressions, propose minimal repairs, validate them deterministically and write the investigation outcome back to DataHub.

## Project status

**Phase 1: deterministic regression gate — in development.**

The current implementation intentionally covers only the first foundation:

- compare an approved baseline metric with a candidate metric;
- support metrics where either higher or lower values are preferable;
- fail when the adverse change exceeds a configured tolerance;
- emit a stable JSON artefact for later diagnosis stages;
- run linting and tests in GitHub Actions.

DataHub connectivity, root-cause ranking, patch generation, repair validation and metadata write-back are roadmap items and are not yet claimed as implemented.

## Planned workflow

```text
Pull request opened
        ↓
Deterministic model evaluation detects a regression
        ↓
ModelGuard gathers changed-code and metric evidence
        ↓
DataHub supplies lineage, schema, ownership and quality context
        ↓
The agent ranks evidence-backed root-cause hypotheses
        ↓
A minimal repair and regression test are generated
        ↓
Independent validation reruns tests and model evaluation
        ↓
A review-ready report is posted and the outcome is written to DataHub
```

## Quick start

### Requirements

- Python 3.11 or later

### GitHub Codespaces

The repository includes a development-container configuration. A newly created or rebuilt Codespace installs the project and runs the quality checks automatically.

For an already-running Codespace, run:

```bash
source scripts/bootstrap_codespace.sh
```

The bootstrap script:

- discovers the active Python installation's scripts directory;
- adds that directory to the current `PATH` and persists it in `~/.bashrc`;
- installs the project and development dependencies;
- runs Ruff and pytest.

This prevents warnings caused by `modelguard`, `pytest` or `ruff` being installed outside the current shell's `PATH`.

### Local installation

```bash
git clone https://github.com/buriro-ezekia/modelguard-datahub.git
cd modelguard-datahub
python -m venv .venv
```

Activate the environment, then install the development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Run the tests

```bash
python -m ruff check .
python -m pytest
```

## Evaluate a metric

The following command compares a candidate F1 score with its approved baseline and writes a machine-readable artefact:

```bash
python -m modelguard evaluate \
  --metric f1_score \
  --baseline 0.842 \
  --candidate 0.771 \
  --max-regression 0.02 \
  --output artifacts/evaluation.json
```

After running the Codespaces bootstrap or activating a correctly configured virtual environment, the shorter console command is also available:

```bash
modelguard evaluate \
  --metric f1_score \
  --baseline 0.842 \
  --candidate 0.771 \
  --max-regression 0.02 \
  --output artifacts/evaluation.json
```

The command exits with status `1` when the regression exceeds the tolerance, making it suitable for a CI gate. A successful comparison exits with status `0`.

Example output:

```json
{
  "baseline": 0.842,
  "candidate": 0.771,
  "change": -0.071,
  "direction": "higher_is_better",
  "maximum_allowed_regression": 0.02,
  "metric": "f1_score",
  "regression_amount": 0.071,
  "status": "failed"
}
```

JSON values are normalised to remove insignificant binary floating-point noise while the regression decision continues to use the original numerical values.

For error metrics such as RMSE, use:

```bash
python -m modelguard evaluate \
  --metric rmse \
  --baseline 2.0 \
  --candidate 2.8 \
  --max-regression 0.5 \
  --direction lower_is_better
```

## MVP demonstration target

The first end-to-end demonstration will introduce an unsafe feature transformation that reduces a model's F1 score. ModelGuard will be expected to:

1. detect the regression deterministically;
2. trace the affected feature and upstream assets through DataHub;
3. rank the modified transformation as the most likely cause using cited evidence;
4. generate a minimal guarded repair and regression test;
5. rerun validation and recover the metric within tolerance;
6. produce a review-ready report and write the resolution context to DataHub.

## Roadmap

- **Phase 1:** deterministic CI regression gate;
- **Phase 2:** DataHub SDK and MCP context retrieval;
- **Phase 3:** evidence-backed root-cause ranking;
- **Phase 4:** constrained repair generation and independent validation;
- **Phase 5:** GitHub reporting and DataHub incident or resolution write-back;
- **Phase 6:** hosted demonstration and hackathon submission assets.

## Safety principles

- The agent will not merge its own repair during the MVP.
- Diagnosis and repair will remain separate stages.
- Every root-cause claim must reference collected evidence.
- Generated patches will be restricted by file, line and validation policies.
- A repair will be labelled validated only after deterministic checks pass.

## Licence

Licensed under the [Apache License 2.0](LICENSE).
