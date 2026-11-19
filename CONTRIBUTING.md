# Contributing

Coyote4 changes must preserve clinical traceability, access control and saved
results. Use synthetic examples in issues, tests and review evidence. Report
security vulnerabilities through [SECURITY.md](SECURITY.md).

## Development

Follow [developer setup](docs/getting-started/developer-environment.md) and
[editable workspace development](docs/core/uv-development.md). Install the Git hooks:

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

The PR template records behavior, modules, check results and release impact. Its
checklist covers tests, changelogs, required version updates, documentation and
compatibility. Mark non-applicable items with a reason; routine changes do not
require a version bump before release preparation.
Use the [module guidance](docs/project/contributing.md#module-update-checklist)
for changes to clinical rules, interfaces or deployment. Avoid patient data,
credentials, private environment files and internal discussion in public records.

Issue templates in `.github/ISSUE_TEMPLATE/*.yml` define GitHub forms with text
fields, dropdowns and required answers. Submitted issues remain editable Markdown.
Separate Markdown issue templates are not needed for the same request types.
The Markdown PR template, `.github/pull_request_template.md`, pre-fills a new PR's
description. Templates become available on GitHub after they are merged into the
repository's default branch.

All three issue forms select the
[coyote3 project](https://github.com/orgs/SMD-Bioinformatics-Lund/projects/22)
through `projects: [SMD-Bioinformatics-Lund/22]`. GitHub applies this setting when
the reporter has write access to the project. To include public contributors and
issues opened through the API or CLI, maintainers must configure the project's
**Workflows → Auto-add to project** with repository
`SMD-Bioinformatics-Lund/coyote3` and filter `is:issue`, then save and enable it.
This built-in workflow requires no repository token or Actions runner. It applies
when matching issues are created or updated; enabling it does not import existing
issues. See GitHub's [issue form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
and [auto-add instructions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically).

## Verification and releases

Run relevant package tests and the [fast smoke checks](docs/testing/test-strategy-and-quality-gates.md#fast-smoke-checks).
Substantive clinical, security, persistence and contract changes need focused
regression tests beyond smoke coverage. Full suites remain available for release
validation; CI intentionally runs only inexpensive checks.

Releases use a reviewed PR from `dev` into `master`, semantic versioning, an
immutable version tag and a GitHub release. Follow the
[release workflow](docs/project/releasing.md) for version ownership and validation.
Contributions are distributed under [GPL-3.0-only](LICENSE.txt).
