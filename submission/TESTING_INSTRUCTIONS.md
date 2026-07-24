# Testing Instructions

## Option A — Hosted demonstration

Open:

```text
https://buriro-ezekia.github.io/modelguard-datahub/
```

Use **Replay the incident** or select the six terminal stages individually. The page is static, requires no login and does not collect data.

## Option B — GitHub Codespaces

1. Open the repository in Codespaces.
2. Run:

```bash
source scripts/bootstrap_codespace.sh
python scripts/run_showcase.py
```

Expected terminal summary:

```text
ModelGuard showcase complete
F1: 0.771 -> 0.842
Diagnosis: feature_transformation (1.0)
Repair: validated | guard=True
Publish: GitHub=created DataHub=raised_and_resolved
Repeat: GitHub=noop DataHub=noop
```

The complete outputs are written to `artifacts/showcase/`.

## Option C — Local Python

Requirements:

- Python 3.11 or 3.12;
- Git;
- no DataHub or GitHub credentials for fixture mode.

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

## What fixture mode proves

Fixture mode executes the real detection, diagnosis, repair, validation and publication logic against deterministic DataHub-shaped context and state files. It proves idempotency and safety without contacting external services.

## Live integration boundaries

Live context retrieval is opt-in through the DataHub SDK or MCP Server. Live GitHub/DataHub publication is also opt-in and requires `--apply` plus scoped tokens. No live external write is necessary to evaluate the hackathon submission.

## Troubleshooting

- `modelguard: command not found`: use `python -m modelguard` or rerun `source scripts/bootstrap_codespace.sh`.
- Expected evaluation exit code `1`: the demonstration intentionally begins with a failed F1 gate; the showcase script treats it as expected.
- GitHub Pages returns 404: repository administrators must select **Settings → Pages → Source: GitHub Actions** once after merging the deployment workflow.
