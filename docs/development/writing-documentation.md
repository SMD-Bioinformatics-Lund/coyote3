# Writing and organizing documentation

Documentation must be readable from both the GitHub file tree and the MkDocs site.
Choose the location by the reader's task, then give the page a name that identifies
its subject without requiring the site navigation.

## Choose a section

| Section | Content |
| --- | --- |
| `getting-started/` | Local evaluation and developer environment setup. |
| `user-guide/` | Clinical review, application pages, controls, and finding actions. |
| `administration/` | Accounts, permissions, assays, gene lists, and clinical configuration. |
| `api/` | Authentication, HTTP routes, ingestion requests, and API compatibility. |
| `architecture/` | Runtime boundaries, data flows, persistence, security, and design decisions. |
| `deployment/` | Installation, environment settings, infrastructure, and acceptance. |
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

## Generated references

### Relational diagrams

Diagram content and directed relationships are defined in `scripts/docs/diagrams.json`.
`scripts/render_documentation_diagrams.py` produces the standalone SVGs in
`docs/assets/diagrams/` with consistent typography, card spacing, and connector routing.
Update the source definitions rather than editing generated SVG coordinates.

```bash
.venv/bin/python scripts/render_documentation_diagrams.py
.venv/bin/python scripts/render_documentation_diagrams.py --check
```

Review the rendered diagrams after changing nodes or relationships. Confirm arrow
direction, branch meaning, label placement, and legibility at the documentation page
width. Geometry checks do not establish that a relationship is clinically correct.

### Schema and permission catalogs

| Page | Authoritative source | Generator |
| --- | --- | --- |
| [MongoDB collection contracts](../reference/mongodb-collections.md) | `api/contracts/schemas/` | `scripts/export_collection_contracts_doc.py` |
| [System permission catalog](../administration/permission-catalog.md) | `api/config/bootstrap/rbac/permissions.seed.ndjson` | `scripts/export_permissions_reference.py` |

Change the authoritative source or generator and regenerate these pages. Do not
edit their generated field or permission listings manually.

## Validate documentation

Run these commands from the repository root:

```bash
npm run docs:lint
.venv/bin/python scripts/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
```

For a generated-reference change, also run its generator and the relevant
contract checks. Inspect the rendered section README on GitHub or in a Markdown
preview, as well as the site's navigation.
