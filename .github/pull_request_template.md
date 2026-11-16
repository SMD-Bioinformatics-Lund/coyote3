## Summary

Describe the problem and the resulting behavior. Include a short before/after
example when useful.

## Scope

- Related issue: Fixes #
- Affected modules:
- Change type: fix / feature / refactor / documentation / release

Choose the affected modules: Core, API, Mongo, Frontend, pyClient, Relay, Atlas,
Demo, Deployment or Docs.

## Verification

| Command or check | Result |
| --- | --- |
| | |

Checks not run and reason (or None):

For intentional UI or report changes, include synthetic screenshots or an example.

## Compatibility and rollout

State **None**, or describe affected interfaces, configuration, stored data,
permissions or clinical behavior, with deployment and recovery steps.
For a release PR, link the changelog and validation record.

## Checklist

Check completed items. For anything that does not apply, replace its checkbox
with **N/A** and a short reason. Version bumps belong to release preparation;
keep dependency requirements and release selections consistent whenever they change.

- [ ] Related issue is linked and the target branch is `dev` (release PRs target `master`).
- [ ] Relevant checks passed, results are recorded above, and regression coverage is updated where needed.
- [ ] Root and affected component changelogs describe the changes.
- [ ] Required versions, dependencies, `release.toml`, derived metadata and lock files are consistent.
- [ ] Affected documentation, configuration examples and public contracts are updated.
- [ ] Compatibility, deployment and recovery needs are documented, including clinical or access-control effects.
