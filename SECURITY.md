# Security Policy

## Supported versions

ModelGuard is currently pre-alpha. Security fixes are applied to the latest commit on `main` and to active pull-request branches.

## Reporting a vulnerability

Do not disclose credentials, private DataHub URLs, proprietary metadata or exploitable details in a public issue. Contact the repository owner privately through GitHub before publishing technical details.

A useful report should include:

- the affected ModelGuard version or commit;
- the provider involved (`fixture`, `sdk` or `mcp`);
- reproducible steps using redacted values;
- the expected and observed behaviour;
- the likely security impact.

## Secret-handling rules

- Store DataHub tokens only in environment variables or an approved secret manager.
- Never commit `.env` files, tokens, session cookies or private metadata snapshots.
- Use a scoped DataHub service account for CI/CD.
- Grant read-only access for Phase 2 context retrieval.
- Review generated artefacts before sharing them publicly because schemas, owners and lineage may be sensitive.

## Automated-action boundary

The MVP does not merge generated repairs automatically. Future mutation and write-back capabilities must remain separately permissioned, auditable and subject to deterministic validation.
