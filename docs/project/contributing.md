# Contributing

This page summarizes how to contribute safely and efficiently.

## Basic contribution flow

![Feature delivery flow](../assets/diagrams/feature-delivery.svg)

1. Sync your branch with latest mainline.
2. Implement focused change(s) with tests.
3. Run local quality gates.
4. Update docs for behavior/config changes.
5. Open PR with clear scope and risk notes.

## Required checks before PR

```bash
PYTHONPATH=. .venv/bin/ruff check src api tests scripts
PYTHONPATH=. .venv/bin/ruff format --check src api tests scripts
scripts/quality/run_quality_suite.sh
```

## Module update checklist

Complete the PR template's general description, tags and linked issues, testing
and validation, responsibility fields, and minimum checklist for every PR. Select
each affected module under **Modules affected**, then complete its matching
collapsible checklist. Leave unaffected module sections collapsed. Add a module
section when the provided choices do not cover the change.

Group related files under their owning module, such as reporting, ingestion, the
API, either SDK, documentation, or deployment. Record versions and changelog
treatment in the template's corresponding fields. The named implementer and
validator own the selected modules unless a different module owner is recorded.
List actual reviewers or mark review pending; a name in the PR description does
not request a GitHub review or establish approval. Use **Notes for reviewers** for
specific decisions, risks, and follow-ups.

Name the responsible contributor and record decisions and evidence. Use
**Done**, **Pending**, or **Not applicable with a reason** for each item. A check
that was not run remains a validation gap; it is not a passing result. Link any
deferred work to an issue with an owner and its effect on acceptance or release.

### For every affected module

- [ ] **Scope and owner:** describe the intended behavior, acceptance criteria,
  affected consumers, and contributor responsible for completing the change.
- [ ] **Version decision:** identify the affected release versions and record
  `old -> new`, unchanged with a reason, or deferral to an owned release task.
  Use the existing version authorities described below.
- [ ] **Changelog:** record the user, integration, clinical, or operational effect
  in the appropriate `CHANGELOG.md` release section. Use high-level outcomes,
  compatibility notes, and required operator actions rather than a task log.
  For changes without release impact, record the reason and obtain the existing
  maintainer-approved `skip-changelog-update` label when the PR gate requires it.
- [ ] **Contracts and dependencies:** review affected HTTP/Python interfaces,
  collection schemas, configuration, events, and callers. Update authoritative
  contracts and regenerate derived artifacts when needed. Record compatibility,
  migration, dependency, and licensing impacts or explain why none apply.
- [ ] **Clinical behavior and traceability:** identify changes to finding
  eligibility, transcript choice, classifications, report wording, or saved
  snapshots. Preserve historical artifacts and provenance; obtain the applicable
  clinical review and regression evidence for deliberate changes.
- [ ] **Security and concurrent edits:** verify changed permissions, sample scope,
  CSRF/session behavior, editing leases, revision checks, and audit evidence where
  applicable. Keep patient data, credentials, and private operational data out of
  commits and review artifacts.
- [ ] **Validation:** record actual commands, scenarios, results, and limitations.
  Cover relevant success, failure, regression, and authorization boundaries.
  For UI changes, check light/dark themes, narrow/wide layouts, keyboard use,
  and loading/empty/error states. Assess performance for changed queries or
  rendering paths with evidence proportionate to the change.
- [ ] **Documentation:** update the maintained user, developer, API, or operator
  references affected by the change. Validate links and the strict site build
  for documentation changes; regenerate generated references from their source.
- [ ] **Deployment and recovery:** identify configuration changes, database/index
  migrations, worker coordination, rollout order, health checks, observability,
  and recovery steps. State irreversible effects and restoration requirements.
  For routine changes, record that no special deployment action is required.
- [ ] **Review and completion:** resolve acceptance criteria and required review,
  link remaining follow-ups, and record outstanding risks. Confirm required CI
  checks pass before merge. Do not mark a blocked or unverified item as complete.

Apply only the checks relevant to the change and explain exclusions. Documentation
or template-only updates do not require application tests; they still need the
applicable lint, metadata/link checks, and diff review. Keep deployment execution
and release approval separate from evidence that the code is ready for review.

### Version decisions

Coyote3 has five release version numbers. Review the applicable identities for
each module; do not invent a new version for each internal service or directory.

| Release identity | Authoritative source |
| --- | --- |
| Application, including UI | `application_version` in `release.toml` |
| Core SDK and bundled server | `[project].version` in `pyproject.toml` |
| Python HTTP client | `[project].version` in `clients/python/pyproject.toml` |
| Modern DNA report template | `[dna].version` in `src/coyote3/templates/reporting/modern/manifest.toml` |
| Modern RNA report template | `[rna].version` in the same manifest |

Working changes do not require all five numbers to advance. Version increments
belong to the affected release, and already published artifacts remain immutable.
Shared report HTML, CSS, or font releases affect both template versions; released
report assets also require a new core/server wheel version. An application that
adopts that wheel selects its exact SDK version in `release.toml`. The UI has no
independent release counter; application package metadata is synchronized through
`npm run sync:version` when the application version changes.

See [version identities and release decisions](../sdk/compatibility.md) and the
[report-template release process](../development/report-templates.md#template-bundle-releases)
for compatibility rules and release verification. HTTP API generations, center
configuration formats, clinical-rule revisions, and patient report numbers have
separate meanings; review their compatibility without treating them as substitutes
for software or template versions.

## Shared editor settings

The tracked `.vscode/settings.json` file contains only
shared, non-personal defaults: Python formatting, trailing-whitespace cleanup,
test discovery, and the frontend Vitest/Playwright roots. It does not select an
interpreter, contain credentials, or encode a local path. Personal editor
settings remain untracked.

## Documentation requirement

If you change behavior, configuration, deployment, or API contracts, update corresponding docs in `docs/` in the same PR.

Write documentation from the reader's perspective. Describe the supported
behaviour, configuration, and limits. Keep change notes in release notes and
keep data-transition instructions in a dedicated migration procedure.

Reference pages describe current behavior, ownership, prerequisites, inputs, outputs,
errors, and limitations. Verify technical claims against the implementation. Do not
include task status, completed-work summaries, cleanup notes, speculative features,
or claims of quality unsupported by tests or operational evidence. Keep internal
planning outside the published documentation. Deployment and recovery procedures
may use ordered steps and checklists when they describe actions an operator must take.
Generated contract pages must be updated through their source schemas and generators.

Use standard Markdown callouts so they render in both GitHub and MkDocs:

> [!IMPORTANT]
>
> Keep the callout short and place it directly beside the rule it qualifies.

## Canonical file

The authoritative contribution policy is in `CONTRIBUTING.md` at repository root.
