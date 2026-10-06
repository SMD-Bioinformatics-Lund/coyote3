# Writing and organizing documentation

Documentation must be readable from both the GitHub file tree and the MkDocs site.
Choose the location by the reader's task, then give the page a name that identifies
its subject without requiring the site navigation.

## Choose a section

| Section | Content |
| --- | --- |
| `getting-started/` | Entry point for evaluation, installation, configuration, upgrades and redeployment. |
| `user-guide/` | Clinical review, application pages, controls, and finding actions. |
| `administration/` | Accounts, permissions, assays, gene lists, and clinical configuration. |
| `api/` | Authentication, HTTP routes, ingestion requests, and API compatibility. |
| `architecture/` | Runtime boundaries, data flows, persistence, security, and design decisions. |
| `deployment/` | Installation and update procedures, infrastructure, and acceptance; published under Getting started. |
| `configuration/` | File formats, setting requirements, defaults, examples and application effects. |
| `development/` | Code changes, components, developer commands, and engineering practices. |
| `operations/` | Monitoring, incidents, backups, updates, and data migrations. |
| `reference/` | Domain definitions, input formats, collection schemas, and clinical rules. |
| `testing/` | Test strategy, fixtures, browser checks, and approved load testing. |
| `project/` | Contribution, maintenance, governance, conduct, and license responsibilities. |

Keep architecture decisions in `architecture/decisions/`, migration procedures in
`operations/migrations/`, and evidence-source references in
`reference/knowledgebases/`. Add another subdirectory only when several related
pages need it.

## Name pages and directories

Use lowercase words separated by hyphens for guide filenames and directories.
Use `README.md` as each section's entry page so GitHub renders its contents when
someone opens the directory. The documentation homepage is `docs/README.md`.

Name the subject and operation where needed: `sample-manifest.md`,
`mongodb-setup-and-recovery.md`, and `clinical-rule-migrations.md`. Avoid vague
names such as `current-context.md`, multiple competing `complete` manuals, and
filenames that require an unexplained internal acronym. Architecture decisions
retain their ordered numeric prefixes.

Give every page one descriptive level-one heading. Explain the page's scope near
the start and link to the prerequisite or next procedure where order matters.
Keep a single authoritative procedure for each operation; related overviews
should link to it instead of maintaining another copy of its commands.

## Procedures and reference material

At the first use of a configurable file or resource, link its reference. Explain
what the reader is choosing before showing a command. Identify placeholders,
operator-selected filenames and shell helper variables; do not present them as
application settings. Keep the steps in execution order with an observable result
and a link to recovery guidance where a failed step needs intervention.

Maintain one detailed reference for each supported configuration file or resource:

- Purpose, owner, location and consumers: who edits it and which services use it.
- Format and a small synthetic example, with unfamiliar syntax explained.
- A field table covering name, meaning, accepted values or units, requirement,
  omission behavior and actual default. Keep example values separate from defaults.
- Dependencies and constraints, including conditional requirements and unsupported values.
- Validation, how changes take effect, and whether existing records are affected.
- Links to the procedure that creates or changes it and the underlying contract.

Apply this structure to deployment settings, clinical resources, ingest files,
API requests and user workflows. Explain what becomes unavailable when an optional
resource is absent. Link generated field/schema catalogs for exact contracts; do
not duplicate them in several guides. Check defaults against the code that consumes
them, including Compose substitution and runtime overrides.

## Editorial style

Lead with the application behavior, resource, or operational requirement. Introductions
should establish the subject and its scope without narrating the writing process or
announcing what the page will explain. Describe capabilities precisely; avoid promotional
claims and unsupported assurances.

Use direct instructions for procedures and factual statements for reference material.
Name the relevant action, condition, and result. Keep permissions, prerequisites,
limitations, and clinical distinctions explicit. Documentation should read as a maintained
product reference, not a response to a request or a summary of completed work.

## Maintain navigation and links

Add each page to its section's README with a short purpose, and to `mkdocs.yml`.
Every navigation group, including nested groups, starts with its own README labelled
**Section guide**. Put introductions and prerequisites before procedures, and detailed
reference pages after the workflows they support. Keep the section README tables in
the same reading order as the sidebar; add new pages at their logical position rather
than prepending them above the section guide.
Use relative Markdown links ending in `.md`; avoid site-only paths for links to
other source pages. Use ordinary Markdown tables, lists, and blockquotes so
important information renders on GitHub as well as in the built site.

For a callout, use a blockquote with a standalone bold heading such as `Note`,
`Important`, or `Warning`, optionally followed by a colon and title. The
documentation build converts these headings to native Read the Docs admonitions;
GitHub retains readable blockquotes. Ordinary quotations are not converted.
Code examples inside quotations remain code, not callout markup.

When moving a page, update its incoming links, its relative links to other files
and images, and references in scripts, tests, configuration examples, and CI.
Review fragments when changing headings. Built page URLs follow the source paths,
so moves also require updating links maintained outside this repository.

## Diagrams and generated references

### Relational diagrams

The standalone SVG files in `docs/assets/diagrams/` are the maintained artwork.
Edit those files directly, keeping typography, card spacing, and connector routing
consistent. Documentation builds use the committed SVGs without an artwork generator.

Keep one-off renderers, layout experiments, and intermediate design definitions in
the ignored `.design/` directory. Commit the reviewed artwork; do not make builds,
tests, or authoring instructions depend on private scratch tooling.

Review the rendered diagrams after changing nodes or relationships. Confirm arrow
direction, branch meaning, label placement, and legibility at the documentation page
width. Visual correctness does not establish that a relationship is clinically correct.

### Schema and permission catalogs

| Page | Authoritative source | Generator |
| --- | --- | --- |
| [MongoDB collection contracts](../reference/mongodb-collections.md) | `api/contracts/schemas/` | `scripts/docs/export_collection_contracts_doc.py` |
| [System permission catalog](../administration/permission-catalog.md) | `api/config/bootstrap/rbac/permissions.seed.ndjson` | `scripts/docs/export_permissions_reference.py` |

Change the authoritative source or generator and regenerate these pages. Do not
edit their generated field or permission listings manually.

## Validate documentation

Run these commands from the repository root:

```bash
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
```

For a generated-reference change, also run its generator and the relevant
contract checks. Inspect the rendered section README on GitHub or in a Markdown
preview, as well as the site's navigation.
