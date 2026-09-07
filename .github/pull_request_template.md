## Summary

Describe the problem, the implemented change, and its user or operational impact.

Closes #

## Change type

- [ ] Fix
- [ ] Feature
- [ ] Refactor or maintenance
- [ ] Documentation
- [ ] Deployment or CI

## Validation

List the commands and manual workflows used to validate this change.

```text
# Example: pytest, frontend unit tests, Playwright, build, or focused checks
```

## Risk and rollout

Note any impact on API contracts, MongoDB documents or indexes, permissions, ingest,
Celery tasks, reporting, configuration, or deployment. Include rollback steps when
the change is not trivially reversible.

## Reviewer checklist

- [ ] Behavior is covered by relevant positive and negative tests.
- [ ] Permissions and audit behavior are correct for changed workflows.
- [ ] Contracts, documentation, and `CHANGELOG.md` are updated when applicable.
- [ ] UI changes include loading, empty, error, and responsive states.
- [ ] No credentials, patient identifiers, or clinical production data are included.
- [ ] Screenshots are attached for material UI changes.
