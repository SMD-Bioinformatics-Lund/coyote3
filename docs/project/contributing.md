# Contributing

[CONTRIBUTING.md](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/dev/CONTRIBUTING.md)
defines the contribution process. Start
with one issue, branch from `dev` and target the PR at `dev`. The
[release workflow](releasing.md) covers promotion into `master`, versioning and tags.

For setup, use the [developer environment](../getting-started/developer-environment.md).
For component boundaries, see the [developer guide](../development/developer-guide.md).

## Module update checklist

Include only the evidence relevant to the changed module in the PR:

| Module | Review and verify |
| --- | --- |
| Core and clinical rules | Selection, units, thresholds, missing inputs, assay scope and report reproducibility. |
| API and identity | Request/response contracts, authentication, permission scope and safe errors. |
| Mongo adapter | Stored contracts, indexes, atomicity, audit events and required migrations. |
| Frontend | Shared components, existing theme, accessibility and successful, empty and failed states. |
| Relay, Atlas and Demo | Package independence, input validation, configuration scope and installation safeguards. |
| Client | Supported HTTP contracts, authentication and failure behavior. |
| Deployment | Required settings, mounts, health checks, compatibility and rollback. |
| Documentation | Accurate examples, relative paths, valid links and clear task-based instructions. |

Clinical and access-control changes require an appropriate domain reviewer. Describe
intended behavior and record test results; do not add checklists for unaffected modules.
See [test selection](../testing/test-strategy-and-quality-gates.md) for commands.
