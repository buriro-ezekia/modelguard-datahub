# ModelGuard - Devpost Submission Draft

## Elevator pitch

ModelGuard is a DataHub-grounded production ML agent that detects model regressions, traces the root cause through end-to-end lineage, generates the smallest supported repair, validates it independently and preserves the resolved outcome in GitHub and DataHub without duplicates.

## Inspiration

Production ML failures often begin with ordinary code changes: a transformation loses a boundary check, a schema changes upstream or a data-quality issue reaches a feature pipeline. Conventional CI can tell a team that a metric fell, but it rarely explains why, understands the connected data assets or returns a repair that engineers can trust. We wanted an agent that behaves like a careful ML platform engineer: evidence first, narrow actions, independent validation and a durable audit trail.

## What it does

ModelGuard executes six guarded phases:

1. Detect a metric regression against an approved baseline.
2. Collect DataHub schema, ownership, quality, lineage and deployment context.
3. Generate competing root-cause hypotheses, rank them transparently and abstain when evidence is weak.
4. Generate only a constrained repair strategy supported by the leading diagnosis.
5. Apply the patch to a temporary copy, compile, run targeted tests and rerun the model evaluation.
6. Create or update one marked GitHub pull-request comment and write one resolved DataHub incident lifecycle record.

In the demonstration, direct division in `monthly_spend` drops F1 from 0.842 to 0.771 and creates 37 infinite values. ModelGuard ranks the changed transformation first at score 1.0000, proposes a two-line denominator guard, passes three targeted tests, restores F1 to 0.842, reduces invalid values to zero and records the resolved incident. Repeating publication produces `noop` rather than duplicates.

## How we built it

ModelGuard is a Python 3.11+ command-line agent with typed dataclasses and stable JSON contracts. A provider-neutral context layer supports the DataHub Python SDK, the DataHub MCP Server over Streamable HTTP and deterministic fixtures for CI and public evaluation.

The diagnosis engine separates evidence extraction, candidate generation and ranking. It combines temporal proximity, lineage relevance, metric explanation, quality corroboration and field specificity, while applying counter-evidence and evidence-diversity penalties.

The repair layer uses Python AST analysis for the demonstrated guarded-division strategy. A patch guard limits the change to one cited Python file, denies protected paths and enforces strict line budgets. Validation runs inside a temporary workspace and reuses the original metric policy.

The publication layer uses hidden delivery markers and stable identifiers to make GitHub comments and DataHub incident write-back idempotent. The hosted demo is a dependency-free static site deployed through GitHub Pages. GitHub Actions verifies linting, tests, the full six-phase showcase and submission assets.

## Challenges we ran into

The hardest problem was deciding where agent reasoning should stop and deterministic control should begin. A plausible explanation is not enough to author code, and a passing unit test is not enough to claim a model repair. We separated diagnosis, generation, validation and publication into independent gates with distinct artefacts and exit statuses.

A second challenge was normalising DataHub context across SDK, MCP and fixture providers without losing provenance. The solution was a provider-neutral context snapshot whose evidence retains source attribution.

The third challenge was safe write-back. CI reruns should not create duplicate pull-request comments or incidents. Stable delivery markers and explicit publication permission made the outcome predictable and auditable.

## Accomplishments

- Complete Phase 1 to Phase 6 flow with deterministic evidence at every boundary.
- DataHub usage across lineage, schema, quality signals, model and deployment context, plus resolved incident write-back.
- Transparent root-cause ranking with supporting and counter-evidence identifiers.
- Explicit abstention instead of forced diagnosis.
- Minimal two-line repair validated outside the source workspace.
- F1 recovery from 0.771 to 0.842 with zero invalid transformed values.
- Idempotent GitHub and DataHub publication.
- One-command showcase, hosted demo, screenshots and sample outputs.

## What we learned

Agents become more useful when context and authority are treated as separate concerns. DataHub gives ModelGuard the context to understand which assets, fields and deployments matter. Deterministic policies decide whether the agent may diagnose, repair, validate or publish. Counter-evidence is also essential: unchanged zero-value source rows reduced confidence in the source-data explanation because the harmful behaviour began only after the transformation changed.

## What's next

- Add constrained repair strategies for schema compatibility, null handling and feature drift.
- Validate against a live open-source DataHub quickstart in a public integration environment.
- Add signed provenance for generated patches and publication receipts.
- Publish a reusable DataHub Skill for the ModelGuard investigation workflow.
- Support policy-as-code approval rules for organisation-specific ML risk tiers.

## Built with

Python, DataHub OSS, DataHub MCP Server, DataHub Python SDK, GraphQL, GitHub Actions, GitHub Pages, pytest, Ruff, YAML, HTML, CSS and JavaScript.

## Final submission fields

- Project name: ModelGuard: DataHub Production ML Agent
- Challenge category: Production ML Agents
- DataHub technologies: DataHub OSS/Core Platform; DataHub MCP Server; DataHub Python SDK; GraphQL incident API
- Hosted project URL: `https://buriro-ezekia.github.io/modelguard-datahub/`
- Public repository: `https://github.com/buriro-ezekia/modelguard-datahub`
- Demonstration video: `https://youtu.be/S96pbK7k_nc`
- License: Apache License 2.0
