<!-- Complete the description, testing, ownership, and minimum checklist for every PR.
Select affected modules and complete only their checklists. Explain individual items
that are not applicable; do not tick work that was not performed. Use synthetic evidence
and follow CONTRIBUTING.md and SECURITY.md. -->

## General description

<!-- Explain the problem, the resulting behavior, and the user or operational impact.
Include a short before/after example when useful. -->

## Tags and linked issues

- Change type: <!-- Fix / feature / refactor / maintenance / documentation / deployment or CI. -->
- Labels/tags: <!-- List relevant labels and apply them in the GitHub sidebar. -->
- Linked issues: <!-- Use "Closes #123" only when this PR fully resolves the issue. -->
- Related PRs or dependencies:

## Testing and validation

<!-- Record checks actually performed, including relevant positive, negative, permission,
and regression cases. Attach synthetic screenshots for visual changes. -->

| Check or scenario | Result | Evidence or limitation |
| --- | --- | --- |
| <!-- Command or workflow --> | <!-- Passed / failed / not run --> | <!-- Output, artifact, screenshot, or reason --> |

- Test environment and build/version:
- Checks not run and remaining limitations:

## Performed by and reviewed by

- Implementation performed by:
- Testing/validation performed by:
- Reviewed by: <!-- Reviewer name and review link, or "Pending". -->
- Additional review needed: <!-- Clinical / security / database / operations, if applicable. -->

<!-- These names describe responsibility; request reviews through GitHub.
Record an approval only after the reviewer has actually submitted it. The listed
contributors own the selected modules unless a different module owner is noted. -->

## Minimum checklist

- [ ] The scope and linked issue's acceptance criteria are addressed.
- [ ] Applicable version decisions are recorded below, including unchanged versions and reasons.
- [ ] Release-facing changes are recorded in CHANGELOG.md, or a maintainer-approved exemption is documented.
- [ ] Tests and validation results, including failures or gaps, are recorded above.
- [ ] Affected contracts, generated artifacts, and documentation are updated or explained.
- [ ] All selected module checklists are completed; exclusions and follow-ups have reasons and owners.
- [ ] Examples, fixtures, logs, and screenshots contain no patient data, real identifiers, credentials, or private operational data.

Version decision(s): <!-- Application / core SDK / client / DNA / RNA: old -> new,
unchanged with reason, or an owned, linked release task. No new per-module counters. -->

Changelog entry or exemption: <!-- Release section/entry, or reason and approved skip-changelog-update label. -->

## Modules affected

<!-- Select every affected module, then complete its matching checklist below.
Leave unaffected module sections collapsed. Add a section for any module not covered. -->

- [ ] Frontend / UI
- [ ] API / core SDK
- [ ] Python HTTP client
- [ ] DNA report template
- [ ] RNA report template
- [ ] Ingestion / background jobs
- [ ] Database / center configuration
- [ ] Security / access control
- [ ] Documentation
- [ ] Deployment / CI

## Module checklists

<details>
<summary>Frontend / UI</summary>

- [ ] Light/dark themes, narrow/wide layouts, keyboard access, and loading/empty/error states are checked.
- [ ] API calls, permissions, query/cache behavior, and editing state are preserved or deliberately tested.
- [ ] The application/UI version decision is recorded; mirrored package metadata is synchronized when required.

</details>

<details>
<summary>API / core SDK</summary>

- [ ] Request/response validation, error handling, permissions, and affected consumers are verified.
- [ ] Authoritative contracts and generated types/references are updated where needed; Python compatibility is reviewed.
- [ ] The core SDK version decision and application's exact SDK selection are recorded; package verification is included when applicable.

</details>

<details>
<summary>Python HTTP client</summary>

- [ ] Affected sync/async behavior, authentication, transport errors, and HTTP contracts are tested.
- [ ] Supported Python interfaces and compatibility with the target API are reviewed.
- [ ] The independent client version decision and client documentation are updated as applicable.

</details>

<details>
<summary>DNA report template</summary>

- [ ] DNA HTML and PDF output, formatting, pagination, and applicable clinical regressions are checked with synthetic data.
- [ ] The DNA template version decision and required core/server package release are recorded.
- [ ] Existing issued reports and snapshots are preserved; shared HTML/CSS/font changes also receive RNA review and version assessment.

</details>

<details>
<summary>RNA report template</summary>

- [ ] RNA HTML and PDF output, formatting, pagination, and applicable clinical regressions are checked with synthetic data.
- [ ] The RNA template version decision and required core/server package release are recorded.
- [ ] Existing issued reports and snapshots are preserved; shared HTML/CSS/font changes also receive DNA review and version assessment.

</details>

<details>
<summary>Ingestion / background jobs</summary>

- [ ] Changed input validation, failure handling, retries, and duplicate-processing behavior are verified.
- [ ] Task/database compatibility, audit evidence, and worker coordination are reviewed.
- [ ] Required synthetic ingestion or full-stack validation is run manually and its outcome recorded.

</details>

<details>
<summary>Database / center configuration</summary>

- [ ] Collection/configuration contracts, indexes, validation, and affected readers/writers are reviewed.
- [ ] Required migrations, deployment order, backup/restore needs, and irreversible effects are documented.
- [ ] Changes are verified with synthetic data and relevant historical-state compatibility checks.

</details>

<details>
<summary>Security / access control</summary>

- [ ] Authorized and unauthorized paths, sample scope, and applicable session/CSRF behavior are tested.
- [ ] Editing leases, revision checks, audit records, and sensitive-data handling are verified where affected.
- [ ] Required security review is recorded; vulnerability details follow the private reporting policy.

</details>

<details>
<summary>Documentation</summary>

- [ ] Instructions and examples match current code, contracts, configuration, and supported commands.
- [ ] Applicable Markdown/link checks and strict documentation build pass; built anchors and assets are checked.
- [ ] Generated references are regenerated from their authoritative source, when affected.

</details>

<details>
<summary>Deployment / CI</summary>

- [ ] Affected builds, environment settings, Compose configuration, health checks, and worker compatibility are verified.
- [ ] Workflow triggers, token permissions, and manual-only ingestion controls are reviewed.
- [ ] Deployment verification, recovery steps, and relevant application/package version decisions are recorded.

</details>

## Rollout and recovery

<!-- State special deployment steps, configuration/migration order, verification,
and recovery limits. For routine changes, state that no special action is required.
Reverting code does not automatically reverse persisted data changes. -->

## Notes for reviewers

<!-- Identify the decisions and files needing particular attention, risks, known
limitations, follow-up issues with owners, and any unmet acceptance criteria. -->
