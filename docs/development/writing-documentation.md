# Write and maintain documentation

Document the behavior implemented by the current code. Each task needs one clear
procedure; detailed fields and contracts belong in references. Documentation does
not establish clinical validation or release approval.

## Choose a section

| Location | Audience and content |
| --- | --- |
| `user-guide/` | Reviewers: samples, findings, comments and reports |
| `administration/` | Administrators: accounts, assays, gene lists and rules |
| `deployment/` | Operators: installation, upgrades and deployment requirements |
| `operations/` | Operators: maintenance, incidents and recovery |
| `configuration/` | Configuration file formats and their consumers |
| `api/` | Integrators: authentication, requests and submission workflows |
| `core/` | Developers: package integration and trusted hosts |
| `development/` | Contributors: development tools and implementation conventions |
| `testing/` | Test selection, fixtures and validation procedures |
| `architecture/` | Ownership, data flow and architecture decisions |
| `reference/` | Exact fields, input formats and domain behavior |
| `project/` | Contributions, releases, licensing and governance |

Package-owned instructions stay in that package's `docs/`. Root documentation
covers the complete application and interactions between packages. For separately
maintained services, keep a short introduction and one external documentation link
in [Packages and integrations](../core/README.md). Link to that introduction elsewhere;
do not recreate the external repository's manual or sidebar here.

## Name pages and directories

Use lowercase hyphenated filenames and one descriptive level-one heading.
Use the section's existing `README.md` as its entry page. Add a page only when it
answers a distinct question; expand an existing page when the material belongs there.
Avoid competing overview manuals and pages that only forward readers to another index.

## Procedures and reference material

Start a procedure with the access, inputs or services it requires. Then give the
actions in order, the result to check and what to do if a step fails. Use the UI's
actual labels and explain unfamiliar terms at first use.

A field reference should state its purpose, accepted values, units, default,
omission/null behavior and constraints. Distinguish examples from application
defaults. Preserve the difference between missing data and measured zero.
Keep one authoritative field table rather than repeating it in several guides.

## Editorial style

Use **Coyote Core** for the core package and **Coyote pyClient** for the external
Python HTTP client. Keep documented commands, paths and configuration keys identical
to their implementation.

Use short, direct sentences and concrete actions. Remove repeated explanations,
introductions that only announce the page's contents and unsupported quality claims.
Preserve necessary permissions, prerequisites, failure handling and clinical
qualifications. Describe proposed behavior only in explicitly identified future work.

## Maintain navigation and links

- Put common tasks first and group related references under familiar subject names.
- Link directly to the procedure or section the reader needs. Do not send a task
  through several indexes before reaching its instructions.
- Keep each page in one primary sidebar location. Section READMEs should explain
  which guide to choose without repeating the same links in several lists.
- Keep instructions and diagrams visible. Do not put page content in collapsible
  `details` sections or add a second contents list above a procedure.
- Use relative Markdown links ending in `.md` so source documentation also works
  on GitHub. Validate fragments after changing headings.
- When consolidating pages, update source links, sidebar entries, generated-reference
  introductions and application help links to the retained destination.

Preserve approved logos, badges and theme styles. README badges use Shields.io
`flat` styling with the existing groups, colors and technology logos. Versions and
runtimes come from release/package metadata. Use the shared documentation stylesheet
for presentation; check narrow/wide screens, light/dark themes and print when it changes.

Callouts use a blockquote headed by **Note**, **Important** or **Warning**, optionally
with a title. The documentation hook renders those as theme admonitions; their text
must also be readable on GitHub. Place a warning beside the action it qualifies.

## Retire obsolete content

Compare a candidate page with its implementation and retained reference before
removing it. Preserve unique, supported instructions; remove duplication and dead
assets. An old date alone does not make an architecture decision or supported
migration obsolete. Update application links as well as documentation links.
Screenshots must show the current interface and synthetic data.

## Diagrams and generated references

### Relational diagrams

Maintain reviewed SVGs in `docs/assets/diagrams/`. Use a diagram only when it explains
a relationship or workflow more clearly than text. Keep labels readable at page
width, distinguish optional paths, and explain the key point beside it. The site
provides **Expand diagram** for detail. Do not introduce artwork generators or
cosmetic tests.

### Schema and permission catalogs

| Reference | Owner and generator |
| --- | --- |
| [Collection contracts](../reference/mongodb-collections.md) | Core schemas; `scripts/docs/export_collection_contracts_doc.py` |
| [Permissions](../administration/permission-catalog.md) | Core RBAC catalogs; `scripts/docs/export_permissions_reference.py` |
| [Python interfaces](../core/reference.md) | Supported exports and docstrings; `scripts/docs/export_core_reference.py` |

Change the source or generator and regenerate. Keep detailed generated catalogs as
lookup references; do not copy their contents into task guides.

## Validate documentation

### Cross-check behavior against its owner

Read the consuming code as well as the schema. Confirm actual permissions, defaults,
selection rules, saved state and failure behavior. A valid field does not establish
when or how it is used. Check installation flags against the installer and displayed
controls against the frontend. Do not execute deployment or database writes to
verify prose without authorization.

### Repository checks

From the repository root:

```bash
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
.venv/bin/python scripts/docs/check_built_site.py
.venv/bin/python scripts/docs/check_operational_examples.py
```

The operational-example check validates shell syntax and script paths; it does not
run the commands. The built-site check validates local links, anchors and assets.
Review the affected reading path in the rendered site. Use behavioral tests for
changed executable examples or contracts; do not freeze prose, layout or artwork
in test assertions.
