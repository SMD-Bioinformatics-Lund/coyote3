# Repository instructions

Coyote4 supports clinical genomics review and reporting. Preserve established
clinical behavior and traceability unless the requested change explicitly alters them.

## Ownership and architecture

- `core/src/coyote/`: domain rules, application workflows, contracts and shared
  software defaults. No HTTP, MongoDB or application-host imports.
- `api/src/coyote_api/`: FastAPI composition, authentication, authorization,
  environment loading and transport. Routers delegate to core services.
- `adapters/mongo/src/coyote_mongo/`: persistence implementations of core interfaces.
  Never import the API. API and Mongo ship together as `coyote-server`.
- `clients/python/`: independent HTTP client. Runtime handlers do not import it.
- `services/relay/`: optional ingestion transport, workers and submission tools.
  Shared ingestion logic belongs to core.
- `services/atlas/`: reference resources and publication. `services/demo/`: synthetic
  data and installation guarded by explicitly isolated targets.
- `frontend/`: React presentation, UI defaults and API client abstractions.
- Each component owns its tests and documentation. Root tests cover composed
  behavior, packaging, security and integration boundaries.

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

## Visual consistency

- Preserve the approved appearance across pages, reports, documentation and READMEs.
  A functional fix does not authorize a redesign.
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

## Repository hygiene and documentation

Keep only maintained source, assets, fixtures, tools and documentation with an
identified consumer. Put temporary probes, artwork experiments and coding-session
scripts outside the repository. Preserve operational migration tools while their
upgrade paths remain supported. Do not commit `.design/`, private center settings,
credentials, patient data, real sample identifiers or database exports.

Write concise, factual documentation for its audience. Explain what a component
does, how to use it, its configuration and its limits. Keep package documentation
within that package and cross-component procedures in root docs. Avoid duplicated
instructions, conversational history and unsupported quality claims. Update links
and commands when removing or moving files.

## Contributions and releases

Work one issue at a time on a focused branch from `dev`; target its PR at `dev`.
Record the affected module, behavior change, relevant validation and upgrade impact.
Keep commits cohesive and use the existing hooks. Do not amend unrelated work.
Push or publish only when authorized.

For a release, prepare versions and changelogs on `dev`, open a release PR into
`master`, and tag the approved merged commit as `vMAJOR.MINOR.PATCH`. Create the
GitHub release from that tag. Keep application, component and HTTP versions distinct;
`release.toml` binds the selected components. Follow `docs/project/releasing.md`.

## Remote access and sensitive data

Remote access requires an explicit request identifying the server and the current
task. A hostname, URL, config file or existing session is not authorization. Prefer
local inspection. Never reuse permission from another task.

Authorized remote work is strictly read-only: inspect only necessary non-sensitive
files, metadata, status or explicitly permitted database queries. No file writes,
installs, permissions changes, Git mutations, database writes, service/container
changes, deployments, migrations, elevation or remote AI agents. Do not use another
protocol or an existing terminal to bypass these limits. File retrieval requires
separate authorization. Do not access patient-identifiable data without separate
organizational authorization; never expose credentials or private keys.

If the target, data access or read-only behavior is uncertain, stop that operation.
Draft commands for manual execution when a remote change is needed; never execute
it. Remote permission means specified server + current task + read-only operations.
