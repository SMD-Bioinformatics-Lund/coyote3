# Repository instructions

Coyote4 supports clinical genomics review and reporting. Preserve established
clinical behavior and traceability unless the requested change explicitly alters them.

## Ownership and architecture

- `core/src/coyote/`: domain rules, application workflows, clinical contracts and shared
  software defaults. No HTTP, MongoDB or application-host imports.
- Reusable data models have one authoritative home in `core/src/coyote/contracts/`.
  Core's base installation includes validation and sanitization dependencies;
  reporting and alignment/VCF dependencies are optional extras. The server selects
  both extras explicitly. Do not introduce a second models distribution.
- `api/src/coyote_api/`: FastAPI composition, authentication, authorization,
  environment loading and transport. Routers delegate to core services.
- `adapters/mongo/src/coyote_mongo/`: persistence implementations of core interfaces.
  Never import the API. API and Mongo ship together as `coyote-server`.
- `coyote-pyclient` is an independent repository for external HTTP integrations.
  Do not install it as an application dependency. Client tests belong there.
- `coyote-relay` is an external public repository, pinned by Git commit in uv.
  Base submission uses core and HTTPX;
  optional routes and workers use server composition. Keep Relay source and tests
  in that repository; shared clinical ingestion logic belongs to core.
- Pin the external Relay dependency to a reviewed full Git commit.
  Keep their versions, lockfile and release selection consistent. The default
  application dependency group installs Relay; it is not a server-wheel dependency.
- `services/atlas/`: reference resources and publication. `services/demo/`: synthetic
  data and installation guarded by explicitly isolated targets.
- `frontend/`: React presentation, UI defaults and API client abstractions.
- Each component owns its tests and documentation. Root tests cover composed
  behavior, packaging, security and integration boundaries.
- `install.sh` is the single installation and deployment entry point. Shared
  orchestration belongs in `deploy/installer/`; extend its commands rather than
  adding another launcher. Keep production, development, staging and test profile
  selection consistent, and preserve the demo's independent credentials and storage.
- Automatic backend source reload belongs to local development. Docker backend
  services run directly; apply changes through an explicit restart or rebuild.
  Keep frontend Vite hot updates available in development.

Load deployment configuration once in the API and pass typed, scoped settings to
packages. Keep defaults in their existing authoritative modules; reuse them instead
of creating aliases. Preserve persisted user settings across deployments. Do not
add compatibility shims or patch layers without an explicit requirement.

## Implementation

- Follow `.editorconfig`, Ruff and existing naming and import conventions.
- Use typed interfaces and Google-style docstrings that explain actual behavior,
  units, null handling and expected failures. Avoid filler and repeated type names.
- Validate external inputs at boundaries. Preserve the distinction between missing,
  zero and null. Use established domain errors and centralized HTTP error handling.
- Keep database operations in repositories and clinical rules in core. Preserve
  assay/environment permissions, audit events, transaction boundaries, snapshot
  immutability and report reproducibility.
- Treat API schemas, collection contracts, configuration keys and clinical rule
  syntax as public contracts. Document deliberate changes and their upgrade impact.
- Do not alter clinical wording, tier matching, filtering or assay-specific order
  as a side effect of refactoring.
- Use repository-relative paths in shared commands and documentation. Resolve
  required absolute paths from explicit configuration, package resources or runtime
  locations. Never embed a developer's checkout path or username.

## Preserve established structure and presentation

- Preserve the approved appearance across pages, reports, documentation and READMEs.
  Change layouts, organization, styles or themes only when the user explicitly
  requests that change. A functional fix, cleanup or modernization request does
  not authorize an unrelated redesign.
- Apply the same rule to code and documentation: retain established module
  ownership, naming, public interfaces, navigation, section order and formatting.
  Reuse the existing implementation and patterns. Do not reorganize unaffected
  files, introduce competing conventions or remove useful content incidentally.
- When the user authorizes a structural change, update all affected consumers
  consistently. Compare the result with the existing baseline and correct
  regressions; do not redefine the baseline just to accept a different result.
- Reuse existing components, PageFrame/PageShell, semantic tokens and typography.
  Preserve light/dark themes, accessibility, spacing, states, borders and elevation.
- Keep the purple/orange branding, joined application header/sidebar and existing
  compact controls. Review shared changes across affected consumers.
- README badges retain Shields.io `flat` styling, technology logos, colors and groups.
  Keep approved logo dimensions and placement consistent across package READMEs.
- Reports use the `coyote3` preset and packaged styles from `smd-reports`. Do not
  modify a sibling package without authorization.
- `scripts/branding/generate_logos.py` is the sole maintained logo blueprint.
  Maintain documentation diagrams as reviewed SVG assets; add no artwork generators
  or cosmetic/logo-generation test suites.

## Tests and verification

Use the smallest meaningful checks for the change, then expand only for unresolved
risk. Keep product regression tests for clinical behavior, permissions, persistence,
API contracts and failure handling. Do not add tests that assert source phrasing,
conversation decisions, artwork layout or implementation details alone.

Each test must identify a concrete failure it detects and assert an observable
result against an independently justified expectation. Cover relevant boundaries,
invalid inputs, denied access and failure recovery. Avoid tests that only repeat
implementation constants, mock away the behavior under test or duplicate coverage
without exercising a different failure mode. Test counts and coverage percentages
are diagnostic measures, not quality targets or release approval.

For documentation, keep checks for executable examples, contract/configuration
accuracy, broken links and deployable artifacts. Review prose and visual consistency
without freezing wording, CSS values, file organization or artwork in test cases.
Retain behavioral accessibility and security checks for interactive documentation.

Fast checks from the repository root:

```bash
bash scripts/quality/run_package_tests.sh all --smoke
.venv/bin/python -m pytest -q tests/smoke
npm --prefix frontend run test:smoke
```

Run affected component suites for substantive changes. The comprehensive local
release checks are documented in `docs/testing/test-strategy-and-quality-gates.md`.
GitHub CI runs smoke checks; a green CI result is not clinical release acceptance.
Keep real-database tests opt-in and restricted to explicitly disposable targets.
Run real-service browser tests through `bash install.sh test-browser`, which creates
and removes its own local container stack with synthetic data. Never run browser
tests against production databases, existing deployments or forwarded database
ports. Do not bypass the runner's target, storage or container-ownership checks.

## Repository hygiene and documentation

Keep only maintained source, assets, fixtures, tools and documentation with an
identified consumer. Keep temporary probes in an ignored workspace directory and
remove them when finished. Do not retain one-off backfills, initial-development
migrations, badge generators or authoring experiments. Do not commit private center settings,
credentials, patient data, real sample identifiers or database exports.

Write concise, factual documentation for its audience. Explain what a component
does, how to use it, its configuration and its limits. Keep package documentation
within that package and cross-component procedures in root docs. Avoid duplicated
instructions, conversational history and unsupported quality claims. Update links
and commands when removing or moving files.

## Contributions and releases

Changelog version headings, tags and release titles always use `vMAJOR.MINOR.PATCH`;
Python and Node package metadata retain unprefixed package versions.

Work one issue at a time on a focused branch from `dev`; target its PR at `dev`.
Record the affected module, behavior change, relevant validation and upgrade impact.
Keep commits cohesive and use the existing hooks. Do not amend unrelated work.
Push or publish only when authorized.

For a release, prepare versions and changelogs on `dev`, open a release PR into
`master`, and tag the approved merged commit as `vMAJOR.MINOR.PATCH`. Create the
GitHub release from that tag. Keep application, component and HTTP versions distinct;
`release.toml` binds the selected components. Follow `docs/project/releasing.md`.

## Workspace and resource boundaries

The current workspace is the default boundary for task data and file operations.
Do not inspect, enumerate, read, create, change or delete files outside it without
explicit authorization for the resource and operation. This includes sibling
checkouts, home directories, mounted storage, system configuration and temporary
directories outside the workspace. Do not follow a symlink outside the boundary.
Use relative paths or resolve paths from the workspace; check the resolved target
before acting. Keep temporary task artifacts inside an ignored workspace directory.

Do not contact servers, databases, APIs, container daemons or other services unless
the user explicitly authorizes access for the task. A URL, connection string,
configured path, existing session or reachable endpoint does not grant permission.
Writing an installer or connection configuration does not authorize running a
deployment, connecting to its targets or changing service state. Test those paths
with synthetic configuration and mocked processes unless execution is authorized.

Requested public documentation research is limited to the relevant public sources.
Never send workspace files, credentials or clinical information to those sources.
Using an installed development tool does not authorize inspecting unrelated user
files or application state. Do not change tool settings or use another protocol,
shell session or privilege level to expand the authorized scope.

Keep credentials and patient-identifiable information out of output, logs, commits
and external services. Access such data only with the required explicit authority.
If an operation needs an additional resource, explain which resource is needed,
why, and whether it would be read or changed. Complete independent workspace work
while that access remains unresolved. Permission for one operation does not extend
to unrelated resources or later tasks.
