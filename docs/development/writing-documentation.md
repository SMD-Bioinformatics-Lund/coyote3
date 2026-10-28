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
| `sdk/` | Application SDK and independent HTTP client installation, use, extension, and version compatibility. |
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

Keep navigation task-based. Put the section's **Start here** entry first, followed
by procedures and their supporting references. Group long menus by operation;
do not make readers choose between several generic manuals without explaining
their differences. Keep each page in one primary sidebar location and use links
from other task guides when it is relevant there too.

Section landing pages should identify the first procedure, prerequisites and the
next related task. Long references should link directly to common operations and
distinguish similarly named concepts, such as query rules, review filters,
reporting rules and report templates. Preserve existing page URLs and heading
fragments when reorganizing navigation. Validate rendered navigation, including
the clinical shortcuts, as well as Markdown links.

Link directly to the relevant procedure or heading in instructions. A section
README is an optional subject index, not a prerequisite between two task steps.
Keep the reader's current operation explicit: prerequisites, ordered actions,
observable result, and recovery when a step fails. Explain a term briefly at first
use before linking its reference; do not make readers leave a procedure just to
discover what its next action means.

`docs/reading-paths.yml` defines the site's explicit task sequences. Add a page there
only when it is the next operation in that task; alternative DNA/RNA guides, worked
examples and field catalogs remain optional references. Sidebar group headings
expand without navigating. Page contents are local and collapsible. The normal
global Next/Previous sequence is replaced by named task navigation.

In-page reference links retain a session-local return location. The return control
leads to the source paragraph; it does not replace browser history or change the
linked resource's URL. Links and task navigation remain usable without JavaScript;
when session storage is unavailable, readers can use browser Back.

Use an existing README for each documentation section. Small task groups within
the sidebar can point directly to their procedures; they do not require another
landing page. Put prerequisites before procedures and detailed references after
the workflows they support. Keep the landing page's reading path consistent with
the sidebar, and place new pages alongside related tasks.
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

## Retire obsolete content

Keep one maintained destination for each procedure or contract. Before removing
a page, compare its instructions with the current code and move any unique,
supported information to that destination. An old publication date alone does not
make a supported migration procedure, architecture decision or reference obsolete.

Update navigation, task paths, in-page references and application help links to the
maintained destination, including the relevant section anchor. Remove duplicated
overview pages instead of keeping intermediate pages whose only purpose is to
send readers to another index. Remove assets that are no longer referenced.

Screenshots must match the documented interface and use synthetic data. Remove
outdated captures from procedures when they conflict with current controls;
retain the written steps and maintained diagrams. Generated references are owned
by their schemas and generators, so change the owner and regenerate when retiring
generated content.

Run the source-link checks, strict site build and built-site checks below after
deletions. Verify the affected reading path in the rendered site.

## Diagrams and generated references

### Relational diagrams

Choose a layout for the question. Use responsibility lanes for human/application/
persisted evidence, grouped dependency maps for runtime and resources, branching
diagnostic maps for missing results, and fan-in/fan-out views for report inputs and
outputs. Reserve a simple chain for a truly sequential procedure. Do not reuse a
linear chain to imply that independent resources or optional paths are required.
Keep required and optional edges distinct in text as well as line style.

The standalone SVG files in `docs/assets/diagrams/` are the maintained artwork.
Edit those files directly, keeping typography, card spacing, and connector routing
consistent. Documentation builds use the committed SVGs without an artwork generator.

Keep one-off renderers, layout experiments, and intermediate design definitions in
the ignored `.design/` directory. Commit the reviewed artwork; do not make builds,
tests, or authoring instructions depend on private scratch tooling.

Review the rendered diagrams after changing nodes or relationships. Confirm arrow
direction, branch meaning, label placement, and legibility at the documentation page
width. Visual correctness does not establish that a relationship is clinically correct.

The site supplies an **Expand diagram** viewer with keyboard dismissal and an
original-SVG link. Each diagram still needs a nearby written explanation for readers
who do not use the visual. Use a viewBox, title/description and legible text at the
page's actual display width; avoid relying on color alone.

### Schema and permission catalogs

| Page | Authoritative source | Generator |
| --- | --- | --- |
| [MongoDB collection contracts](../reference/mongodb-collections.md) | `src/coyote3/contracts/schemas/` | `scripts/docs/export_collection_contracts_doc.py` |
| [System permission catalog](../administration/permission-catalog.md) | `api/bootstrap/catalogs/rbac/permissions.seed.ndjson` | `scripts/docs/export_permissions_reference.py` |

Change the authoritative source or generator and regenerate these pages. Do not
edit their generated field or permission listings manually.

## Validate documentation

### Cross-check behavior against its owner

Read the consuming code, not just the schema or an older guide. A valid field does
not establish when it is applied, which permissions are required or what is saved.

| Documentation area | Code to cross-check | Evidence to retain |
| --- | --- | --- |
| Deployment and upgrades | `scripts/deployment/`, `deploy/compose/`, `api/config/` | Shell syntax, real script flags, Compose precedence, environment defaults and rollback boundaries. Do not execute writes just to validate prose. |
| Accounts and access | `api/security/`, `src/coyote3/application/operations/`, RBAC seed catalogs | Role responsibilities, route permissions, sample scope and temporary-password behavior. |
| Assays and configuration | `src/coyote3/contracts/schemas/`, `src/coyote3/application/resources/` | Required versus optional resources, Base fallback, scope immutability and activation checks. |
| Finding selection | `src/coyote3/application/query_rules/`, `src/coyote3/domain/dna/`, `src/coyote3/domain/rna/` | Application base gates, inheritance, exceptions, sample-filter references and post-filters. |
| Reporting | `src/coyote3/application/reporting/`, `src/coyote3/templates/reporting/` | Suggestion versus saved comment, eligibility, preview/save boundaries and resolution receipts. |
| Ingest formats | `src/coyote3/application/ingest/`, collection contracts | Parse downloadable examples through the actual adapters and validate the resulting documents. |
| HTTP and Python interfaces | Route modules, generated OpenAPI, `clients/python/`, supported operations | HTTP methods/paths, authorization, import boundaries and release compatibility. Hidden internal routes must also be checked in route source. |
| Navigation and diagrams | `mkdocs.yml`, reading paths, rendered HTML and SVGs | Direct procedure destinations, anchors, return context, keyboard controls, readable labels and correct dependency direction. |

Structural checks do not prove clinical suitability, deployment readiness or external
website availability. Validate clinical changes with the affected domain tests and
review representative center workflows separately.

### Repository checks

Run these commands from the repository root:

```bash
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
.venv/bin/python scripts/docs/check_built_site.py
.venv/bin/python scripts/docs/check_operational_examples.py
```

For a generated-reference change, also run its generator and the relevant
contract checks. Inspect the rendered section README on GitHub or in a Markdown
preview, as well as the site's navigation.

After building the site, the browser reading-flow checks run with:

```bash
npm --prefix frontend run test:e2e -- docs-reading.spec.ts
```

These serve the local generated site through browser fixtures. They do not connect
to application databases or a deployed documentation server. Check a narrow screen,
both reading themes, keyboard diagram dismissal, a procedure-to-reference round trip,
and direct task continuation.
