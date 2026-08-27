# Maintainer guide

Maintainers protect the stability of the clinical workflow, data contracts,
security boundaries, and release process.

## Change rules

| Rule | Required practice |
| --- | --- |
| Preserve behavior | Change an existing workflow only when the change is intentional, tested, and documented. |
| Use explicit contracts | Validate API and MongoDB boundaries with declared models. Do not depend on undocumented document shapes. |
| Keep one source of truth | Do not copy configurable values or fixed vocabularies into feature modules. |
| Test risk | Cover the success path, failure path, and permission boundary affected by the change. |
| Protect security | Never bypass authentication, authorization, CSRF, audit, or secret handling for development convenience. |
| Keep the branch healthy | Required CI checks must pass before merge. |

## Pull request sequence

1. Define or update the domain behavior.
2. Update application services and persistence contracts.
3. Expose the behavior through the HTTP interface when required.
4. Update the frontend through shared API and UI components.
5. Add focused tests at each changed boundary.
6. Update the authoritative documentation.
7. Run the affected quality checks.

The [complete developer manual](../developer/complete_developer_manual.md)
explains where each responsibility belongs.

## Review checklist

| Area | Review question |
| --- | --- |
| Correctness | Does the implementation satisfy the stated behavior for positive and negative cases? |
| Clinical state | Can saved classifications, filters, comments, and reports still be reconstructed? |
| Access | Are route permissions, target-resource scope, and delegated administration enforced? |
| Persistence | Do repositories and Pydantic contracts own database access and validation? |
| Failure handling | Does failure leave the sample or resource in a valid state and create the required audit evidence? |
| Performance | Are indexes, pagination, caching, and query cardinality appropriate for production data? |
| Tests | Do tests prove behavior rather than internal implementation details? |
| Documentation | Is the current behavior described without release-note language? |

## Local verification

```bash
PYTHONPATH=. ruff check api tests scripts
PYTHONPATH=. pytest -q
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
npm --prefix frontend run lint
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm run docs:lint
.venv/bin/python -m mkdocs build --strict
```

Run affected Playwright suites for user-facing changes. Run disposable
full-stack validation for changes to ingest, deployment, authentication,
background tasks, or reporting.

## Merge and release

- Require the protected quality check.
- Resolve review comments before merge.
- Keep commits coherent and avoid unrelated generated-file changes.
- Use versioned immutable images for releases.
- Record user-visible changes in the changelog.
- Retain the evidence required by the release-readiness guide.

See [release readiness](../operations/release_readiness.md) for the complete
release decision.
