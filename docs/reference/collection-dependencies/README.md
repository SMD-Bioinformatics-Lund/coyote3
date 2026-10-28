# Collection dependencies and migration planning

Use this reference to answer **which stored field points to which collection key**,
what must exist before a document is usable, and which downstream records are
affected by a key change. Each collection has an SVG diagram, outgoing dependencies,
incoming references, relationship semantics, and source-code evidence.

The inventory covers the physical bindings in `api/config/collections.toml` and
the operational collections in `api/config/operational_collections.py`. It is a
source-code reference, not an inspection of a particular server. Operator archives,
temporary import collections and historical collections outside these bindings
must be inventoried separately before migration. No database is read or changed
when this reference is generated.

## Find a collection or workflow

| Start here | What it explains |
| --- | --- |
| [Complete collection inventory](inventory.md) | Every database-qualified collection, its binding and detailed dependency section. |
| [Assays, diagnoses and gene lists](configuration.md) | ASP/ASPC, assay groups, named diagnoses, associations, lists, blacklist and coverage exclusions. |
| [Drafts, publications and revision history](workflows.md) | Setup staging, configuration profiles/promotions, rule versions, revision snapshots and public catalogs. |
| [Samples, findings, annotations and reports](clinical.md) | All ten sample evidence collections, shared VEP records, comments, clinical annotations and report-time snapshots. |
| [Identity, permissions and audit](identity.md) | User/role/permission identifiers, sessions, historical actors and integrity chains. |
| [Knowledgebase and reference evidence](knowledgebase.md) | HGNC/VEP, provider identifiers, coordinate/transcript lookups, COSMIC product payloads and release manifests. |
| [Operational state and BAM records](operations.md) | Ingest jobs, notifications, cursors, edit leases, artifact cleanup and external BAM identifiers. |

For a specific migration, combine this target-model reference with the
[clinical data migration procedure](../../operations/migrations/clinical-data.md#select-the-source-version).
It defines source-specific transformations and supported commands for Coyote v2
and v3. Do not infer source schema
or conversion rules solely from a target collection name.

## Read the diagrams correctly

Each arrow runs **source collection.field → target collection.key**. Open the
full-size SVG when a collection has many incoming references. The accompanying
tables carry conditions that cannot be expressed by one arrow.

| Relationship | Meaning for migration |
| --- | --- |
| BSON ObjectId | Preserve both the value and BSON type. A hexadecimal string is not equal to an ObjectId in a MongoDB equality join. |
| String ObjectId / string identity | Stored textual representation of a parent `_id`; convert explicitly when validating against BSON parent identities. |
| Business key | A string such as `asp_id`, `isgl_id`, `username` or `permission_id`. Do not replace it with a display label or MongoDB `_id`. |
| Exact revision | Points to the particular retained document, not the current active revision of the same business resource. |
| Composite lookup | All listed keys and the stated context participate; one key alone is insufficient. |
| Conditional / polymorphic reference | The target depends on a discriminator, scope or state. Null may be valid. Validate the condition before declaring an orphan. |
| Snapshot / provenance | Historical content or attribution is retained. It must not be refreshed from a newer live target during migration. |
| Vocabulary / evidence lookup | Gene, transcript, coordinate or provider identity matching; not a database-enforced parent-child relationship. |
| Release manifest | A document names a product collection. It does not assign every row an implicit `release_id` foreign key. |
| Operational key / cursor | Temporary ownership, deduplication or recovery state. Decide whether to retain, reconcile or deliberately reset it; do not treat it as clinical history. |

`[]` means an array member; `{name}` means a dynamic dictionary key. `+` denotes
the keys participating together or the explicitly listed related fields; the
semantics column states which. `OR` and `/` mark alternatives. Multiplicity is the
application relationship, not a promise of a unique MongoDB index. For example,
many retained ASP revisions can have one `asp_id`; select the required version or
the current active document according to the operation.

MongoDB does not enforce these arrows as SQL foreign keys. Application validation,
repository predicates, unique indexes, hashes and transaction boundaries provide
different parts of the integrity checks. A valid Pydantic document alone does not
prove that all referenced resources exist.

## Keys most likely to be confused

| Stored key | Actual target or meaning | Not interchangeable with |
| --- | --- | --- |
| `variants.SAMPLE_ID` and the other evidence `SAMPLE_ID` fields | `str(primary.samples._id)` | Sample name, case ID, or a BSON ObjectId inserted into the same string field. |
| `sample_comments.sample_oid`, `finding_comments.sample_oid`, `reports.sample_oid` | BSON `primary.samples._id` | The evidence collections' string-valued `SAMPLE_ID`. |
| `finding_comments.finding_oid` | The finding `_id` chosen by `finding_type` | Annotation ID or an unqualified variant ID. |
| `samples.current_aspc_id` | The exact retained `asp_configs._id` | Latest ASPC, `aspc_id`, or a display name. |
| `samples.current_aspc_name` | Captured ASPC display name, falling back to `aspc_id` | A reliable foreign key. |
| `annotation.genomic_hash` | Genomic identity hash paired with `genomic` | `variants._id` or a sample-owned annotation pointer. |
| `anno_vep.simple_id_hash + vep_version` | Shared immutable transcript-vault identity | A variant's sample ID or the latest available VEP version. |
| `clinical_rule_sets.content_version` versus `revision` | Clinical release versus mutation counter within a content-version document | The rule-set MongoDB `_id`. |
| `public_assay_catalog.resource_revisions.*.configuration_id` | ASPC business key, paired with `configuration_revision` | `asp_configs._id`. |
| `api_sessions.user_id` | `identity.users.username` | `users._id`. |
| `bam.samples.id` | Case/control material identifier | `primary.samples._id`; these are separate databases. |
| `blacklist.assay` | Physical scope key; migration bundle `assay_group` is translated to it | An additional physical field that can be copied without conversion. |

The implicit diagnosis `base` has no required `diagnoses` record. Gene-list
`diagnosis[]` tags do not create assay/diagnosis associations. A draft assay setup
can precede the operational ASP: it is a publication candidate, not an orphan.

## Snapshots, authors and hashes

Revision collections embed their parent's document under `document`. The embedded
paths inherit the parent's relationships with that prefix, but describe the
historical revision. For example:

```text
assay_setup_revisions.document.content.panel.asp_group
  → assay_groups.group_id (historical setup context)

clinical_rule_revisions.document.scope.asp_id
  → assay_specific_panels.asp_id (historical rule scope)

public_assay_catalog_versions.catalog.modalities.{modality}.categories.{key}.aspc_id
  → asp_configs.aspc_id (draft/publication binding)
```

Preserve embedded content, original identifiers, authors, timestamps, status,
revision numbers and hashes together. Replacing a nested historical document with
the current resource destroys the historical meaning even when its business ID
has not changed. Do not recompute a hash merely to make altered historical content
pass a check. Use the relevant documented migration and keep an auditable account
of any approved transformation.

Common actor fields map to usernames for attribution. `system`, missing historical
attribution and accounts that no longer exist are legitimate cases; they are not
automatically data corruption. Do not fabricate an author or replace every actor
with the operator running the migration. The diagrams omit repeated generic actor
arrows for readability; the outgoing and incoming tables retain them.

Report snapshots retain what was reported. Links such as `annotation_oid` and
`var_oid` provide provenance; they are not instructions to regenerate the report
from today's annotations, thresholds or transcript selection. Report HTML/PDF and
other referenced artifacts must be preserved alongside the database records.

## Plan the load in dependency groups

This order describes dependencies, not a command to write to a live database.
Draft activation and publication have their own transaction/review requirements.

| Stage | Prepare or load | Validate before continuing |
| --- | --- | --- |
| 1. Inventory | Source exports, original types/IDs, files, versions and intended target namespaces | Distinguish v2/v3 source schema from this target schema; define duplicate/conflict handling and rollback scope. |
| 2. Shared reference | `vep_metadata`, diagram assets and `hgnc_genes`; applicable evidence releases | Historical VEP release/build/transcript evidence exists. Install reference data using its supported workflow. |
| 3. Identity and configuration | Permissions → roles → users; groups and diagnoses → assays/associations → applicable profiles, lists, rules and exact ASPCs | Check current flags, versions, scope, hashes and dependencies. Historical actors need not become active accounts. Draft dependencies may precede operational publication. |
| 4. Variant transcript vault | Build `anno_vep` from retained v2/v3 transcript annotations | Deduplicate by variant identity and VEP release without losing transcripts or silently reannotating. The source migration's VEP 103 requirement is separate from the runtime's supported versions. |
| 5. Samples and evidence | Preserve sample ObjectIds; load all owned finding/measurement collections | Each `SAMPLE_ID` resolves to its original sample; exact ASPC references and diagnosis/environment context agree. Converters can prepare findings before samples, but the final applied state must have both. |
| 6. Clinical curation | `annotation`, blacklist/exclusions, sample and finding comments | Resolve nomenclature/transcripts and assay scope; preserve original authors/time and comment owner types. Apply the v2/v3 annotation source-selection rules in the migration procedure. |
| 7. Reports and saved findings | `reports`, `reported_variants`, original artifact files | Preserve report IDs, BSON references, saved text/tier and report-time configuration. Restore latest-report pointers only after their targets exist. |
| 8. History and operational reconciliation | Revision documents, audit chains, pending outbox/artifact work, notification read/dismissal state | Check hash chains and exact version ownership. Reauthenticate sessions; do not copy active edit leases into the new environment. Reconcile jobs before replay. |

Some dependency graphs contain intentional cycles: samples point to their latest
report, while reports point back to samples; a setup can reference a rule authored
for its reserved assay before activation. Use staged application and final
validation rather than discarding one side of these relationships.

For clinical configuration renames, inspect **incoming references** on the target
collection before changing a key. This includes stored snapshots and actor/history
records, not only the currently active configuration.

## Read-only validation examples

Run only against an approved source snapshot or migration-validation target. These
examples do not write or repair documents. The logical primary database is selected
explicitly; substitute its actual name locally.

```javascript
const primary = db.getSiblingDB("<primary-database>");

// Distinguish missing/string/ObjectId owner values before attempting joins.
primary.variants.aggregate([
  {$group: {_id: {$type: "$SAMPLE_ID"}, count: {$sum: 1}}}
]);

// String-valued evidence owner → BSON sample identity; malformed values become null.
primary.variants.aggregate([
  {$set: {_owner: {$convert: {
    input: "$SAMPLE_ID", to: "objectId", onError: null, onNull: null
  }}}},
  {$lookup: {from: "samples", localField: "_owner", foreignField: "_id", as: "_parent"}},
  {$match: {$or: [{_owner: null}, {"_parent.0": {$exists: false}}]}},
  {$project: {_id: 1, SAMPLE_ID: 1}},
  {$limit: 20}
]);

// BSON owner references must match without converting the persisted value.
primary.reports.aggregate([
  {$lookup: {from: "samples", localField: "sample_oid", foreignField: "_id", as: "_parent"}},
  {$match: {"_parent.0": {$exists: false}}},
  {$project: {_id: 1, sample_oid: 1}},
  {$limit: 20}
]);
```

Repeat the evidence-owner check for every collection listed under the sample
inventory, not only SNVs/CNVs. Separately check a finding comment's discriminator,
finding existence **and** sample ownership. Reconcile counts by assay and source,
not merely total collection counts. Check duplicate business-key/version pairs and
current/active predicates using the collection's repository indexes.

For cross-database references, read the relevant key sets through their separately
configured clients and compare them in a read-only validation process. Do not
present a same-database `$lookup` as verification of a relationship across different
MongoDB services. A diagram edge also does not mean those clients share a transaction.

## Provider data and known boundary differences

- COSMIC product collections with `record_key` / `source_row` preserve provider
  columns. The contract does not declare foreign keys between every vendor file.
  Their gene/transcript/coordinate relationships require the imported release's
  column definitions. Product availability also depends on active release metadata.
- COSMIC's minimal typed variant record omits some allele columns consumed by the
  richer repository lookup. Inspect the stored product shape when validating an
  allele-level match; matching only a genomic position is not equivalent.
- The OncoKB actionable typed import uses `Hugo Symbol` / `Entrez Gene ID`, while
  the repository lookup queries `Gene`. Confirm the installed importer shape before
  assuming those keys are interchangeable. `onkokb` is the actual configured
  physical name for the licensed annotation collection.
- Blacklist group scope is stored in physical `assay`; the repository indexes
  `(assay, pos)`. The fresh shared-blacklist converter remains to be implemented.
- `asp_to_groups` and `mane_select` have registered schema contracts but no current
  physical binding in `collections.toml`. They are listed separately in the
  inventory; their schema presence alone is not evidence of a required live collection.

These distinctions are documented as observed boundaries. This reference does not
change importers, schemas, clinical matching or database records.

## Maintain this reference

The reviewed source-field mappings, relationship semantics and evidence paths live
in `scripts/docs/collection_dependencies.json`. The generator combines them with
the physical binding inventory and collection schemas, then emits the reverse
references, per-collection SVG diagrams and domain pages. Dynamic provider payloads
are not inferred into foreign keys by their field names.

```bash
PYTHONPATH=.:src .venv/bin/python scripts/docs/export_collection_dependencies.py
PYTHONPATH=.:src .venv/bin/python scripts/docs/export_collection_dependencies.py --check
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
```

When adding a collection or changing a key, update the reviewed mappings and
evidence, regenerate, and review both outgoing and incoming tables. `--check`
detects stale rendered output, unknown namespaces, missing source evidence and
missing leading schema fields; it is not proof that a live database satisfies the
relationships or that a provider's opaque payload has not changed.

[Collection field contracts](../mongodb-collections.md) ·
[Database topology](../../architecture/mongodb-topology.md) ·
[Migration procedures](../../operations/migrations/README.md)
