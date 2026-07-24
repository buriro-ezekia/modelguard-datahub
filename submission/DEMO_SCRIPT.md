# Demonstration Video Script — 2:35 Target

## Recording requirements

- Record at 1080p or higher.
- Keep the browser zoom at 100–110%.
- Do not use copyrighted music.
- Show the software functioning, not only slides.
- Upload publicly to YouTube or Vimeo.

## 0:00–0:15 — Problem and promise

**Visual:** Hosted demo hero and F1 proof cards.

**Narration:**

> A tiny feature transformation can silently damage a production model. ModelGuard turns that failed CI metric into an evidence-backed diagnosis, a minimal validated fix and a resolved DataHub incident—without auto-merging anything.

## 0:15–0:35 — Detect

**Visual:** Select **Detect** in the terminal replay.

**Narration:**

> This churn-model candidate drops F1 from 0.842 to 0.771. The deterministic gate fails with exit code one, giving the rest of the system a structured regression artefact.

## 0:35–0:58 — DataHub context

**Visual:** Select **Context**, then scroll to the architecture diagram.

**Narration:**

> ModelGuard queries DataHub through the MCP Server or Python SDK for schema, ownership, quality signals and bidirectional lineage. It sees the complete path from raw customers through customer features and training data to the model and production deployment.

## 0:58–1:22 — Evidence-backed diagnosis

**Visual:** Select **Diagnose**, show ranked bars and evidence IDs.

**Narration:**

> The agent generates competing hypotheses instead of jumping to a conclusion. The changed feature transformation ranks first at 1.0 confidence because it is on the lineage path, touches the affected fields and explains 37 new infinite values. The unchanged source rows become counter-evidence against blaming source data alone.

## 1:22–1:48 — Constrained repair and validation

**Visual:** Select **Repair** and **Validate**; show the diff card.

**Narration:**

> ModelGuard proposes exactly two lines in one cited function. Guardrails reject protected paths, oversized patches and unsafe tokens. The patch is applied only in a temporary workspace, where compilation, three targeted tests and an independent model evaluation all pass. F1 returns to 0.842 and invalid values fall to zero.

## 1:48–2:08 — Closed-loop publication

**Visual:** Select **Publish** and show GitHub/DataHub cards.

**Narration:**

> The validated-only publication gate creates one review-ready GitHub comment and raises then resolves one DataHub incident. The same delivery ID makes a second execution a no-op, so reruns never spam reviewers or duplicate metadata.

## 2:08–2:27 — One-command proof

**Visual:** Codespaces terminal running `python scripts/run_showcase.py`; show final summary.

**Narration:**

> Judges can reproduce the complete flow with one command and no credentials. Every JSON report, Markdown explanation, diff and incident output is committed under examples.

## 2:27–2:35 — Close

**Visual:** Hosted demo final call to action.

**Narration:**

> ModelGuard: detect the regression, trace the cause, validate the fix and preserve the knowledge with DataHub.
