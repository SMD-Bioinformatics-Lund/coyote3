# Contribution and release workflow

`dev` is the integration branch. `master` contains approved releases. A release
is identified by an immutable `vMAJOR.MINOR.PATCH` tag on the approved master commit.

## Resolve one issue

1. Create or reuse an issue describing the problem, affected module and acceptance criteria.
2. Create a focused branch from current `dev`, for example `fix/123-report-summary`.
3. Implement the change, update relevant documentation and run the affected tests.
4. Open a PR into `dev`. Link the issue, describe the resulting behavior and record
   validation and any configuration or compatibility impact.
5. Obtain review and merge after the smoke checks pass. Close the linked issue when
   its acceptance criteria are satisfied.

Keep unrelated work in separate issues and PRs. Clinical selection, interpretation,
report wording and access-control changes need review by the appropriate domain owner.

## Choose the version

Use semantic versioning for the application and each independently released component:

| Change | Version increment | Example |
| --- | --- | --- |
| Incompatible public contract or required incompatible configuration/data change | Major | `4.2.3` → `5.0.0` |
| Backward-compatible functionality | Minor | `4.2.3` → `4.3.0` |
| Backward-compatible correction | Patch | `4.2.3` → `4.2.4` |

A clinical correction may require validation and an upgrade notice even when its
version increment is a patch. Never move a published tag to a different commit.

`release.toml` records the application version and its exact component selections.
Each distribution owns its version in `pyproject.toml`. The server combines API and
Mongo source trees; those components share its distribution version. Change only
the affected component versions, update selected dependencies and `uv.lock`, and
keep application, package, HTTP API and configuration revisions distinct.
See [release compatibility](../core/compatibility.md) for their responsibilities.

Relay is maintained independently. Adopt its reviewed full Git commit
through `[tool.uv.sources]`, update `uv.lock`, and select its package version in
`release.toml`. The release artifact set contains five wheels: core,
server, Relay, Atlas and Demo. The normal image installs four; Demo is reserved for
the isolated demo target. The Python client is not an application dependency.

Update the root changelog with application highlights and affected package
changelogs with their changes. Synchronize derived metadata from the repository root:

```bash
npm run sync:version
.venv/bin/python -m scripts.release.check_release
```

Update README version badges to match the selected component versions, preserving
their established Shields.io styles, colors and groups.

CI checks versions and changelogs before installing test dependencies. Each PR
must edit `CHANGELOG.md`; a maintainer may waive that edit with the
`skip-changelog-update` label for changes that need no release note. Version
decreases are rejected. Every selected component needs a matching changelog heading,
and changing its version requires an edit to its changelog. The label does not
waive those version-specific requirements.

Ordinary PRs into `dev` may retain their current versions. A release PR into
`master` must increase the application version and the version of each existing
component whose source or build metadata changed. API and Mongo share the server
version and have separate changelogs. This prevents publishing changed wheels
under an existing version. Run the same comparison locally against an available
target commit:

```bash
.venv/bin/python -m scripts.release.check_release --base-ref master --target-branch master
```

## Prepare the release PR

Open a release PR from `dev` into `master`, titled `Release vX.Y.Z`. Include:

- Version and changelog link, with the included issues or PRs.
- Compatibility, configuration and migration requirements, if any.
- Validation results, known limitations and the approval record.

Run the [full local quality gate](../testing/test-strategy-and-quality-gates.md#unified-quality-gate)
and applicable database, browser, deployment and report acceptance checks on the
release candidate. Build the selected wheels and images using the
[artifact procedure](../deployment/application-upgrades.md). Validate the artifacts
that will be promoted; retain their identifiers and the test results.

The GitHub workflow runs inexpensive smoke checks only. It does not replace
clinical validation, database transaction tests, backup/restore rehearsal or
center approval. A failed required check blocks release; document optional checks
that were not applicable rather than recording them as passed.

## Tag and publish

After the release PR is approved and merged, a maintainer verifies the release
commit on `master`, creates the annotated `vX.Y.Z` tag on that commit, pushes the
tag and creates the GitHub release from it. The release notes contain user-facing
changes, upgrade requirements and known limitations; link the reviewed changelog
and approved artifacts. Do not tag the development branch or include internal
review discussions in release notes.

Publication is a maintainer action; this repository does not automatically deploy
or publish Python packages when a tag is created. Deploy through the center's
[upgrade procedure](../deployment/application-upgrades.md), with a verified backup,
rollback plan and recorded acceptance. Merge any release-only corrections back
into `dev` so subsequent work starts from the released behavior.

When configuring branch protection, require the `Smoke checks` job from the
`quality` workflow. Remove requirements for retired job names; CI cannot update
repository protection settings itself.

## Urgent corrections

For an urgent production correction, open an issue and a focused branch from the
released master commit. Use the same review, validation and release requirements;
issue a new patch version and tag. Bring the correction back into `dev`. Never
rewrite the released tag or bypass audit and clinical approval requirements.
