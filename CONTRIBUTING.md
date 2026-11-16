# Contributing

Coyote4 changes must preserve clinical traceability, access control and saved
results. Use synthetic examples in issues, tests and review evidence. Report
security vulnerabilities through [SECURITY.md](SECURITY.md).

## Development

Follow [developer setup](docs/getting-started/developer-environment.md) and
[editable workspace development](docs/sdk/uv-development.md). Install the Git hooks:

```bash
git config core.hooksPath .githooks
```

Each component owns its tests and documentation. Shared workflows belong in core,
HTTP composition in API, persistence in the Mongo adapter and presentation in the
frontend. Reuse established contracts, components and theme tokens. A functional
fix should preserve the approved design.

## Submit a change

1. Create or reuse an issue with the problem, affected module and acceptance criteria.
2. Branch from `dev` and keep the change focused on that issue.
3. Implement and test the change; update the relevant documentation and changelog.
4. Open a PR into `dev`, linking the issue and recording actual validation results.
5. Resolve review feedback before merging.

The short PR template covers behavior, modules, validation and release impact.
Use the [module guidance](docs/project/contributing.md#module-update-checklist)
for changes to clinical rules, interfaces or deployment. Avoid patient data,
credentials, private environment files and internal discussion in public records.

## Verification and releases

Run relevant package tests and the [fast smoke checks](docs/testing/test-strategy-and-quality-gates.md#fast-smoke-checks).
Substantive clinical, security, persistence and contract changes need focused
regression tests beyond smoke coverage. Full suites remain available for release
validation; CI intentionally runs only inexpensive checks.

Releases use a reviewed PR from `dev` into `master`, semantic versioning, an
immutable version tag and a GitHub release. Follow the
[release workflow](docs/project/releasing.md) for version ownership and validation.
Contributions are distributed under [GPL-3.0-only](LICENSE.txt).
