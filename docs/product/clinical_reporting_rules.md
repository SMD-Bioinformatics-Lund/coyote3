# Clinical Reporting Rules

## Purpose

Clinical reporting rules convert a prepared clinical result into governed report
wording. They do not select transcripts, filter findings, assign tiers, or modify
findings. Those decisions are complete before rule evaluation begins.

The authoritative rule source is the `clinical_rule_sets` collection in the primary
application database. Each ASPC binds explicitly to one stable rule-set identity with
`reporting.clinical_rule_set_id`. Runtime report generation does not load rule files,
evaluate arbitrary templates, or fall back to another assay or subpanel.

![Clinical report generation flow](../assets/diagrams/report_generation_flow.svg)

> **Important: classification annotations are separate**
>
> Rule sets produce report narrative only. The optional automatic text used during
> bulk Tier III classification remains finding annotation behavior and is not read
> from an ASPC or clinical rule set.

## Rule-Set Identity And Binding

The stable identity is:

```text
<asp_id>__<subpanel_id>__<language>
```

For example, `hema_gmsv1__base__sv` identifies Swedish reporting rules for the base
subpanel of `hema_gmsv1`. Environment and ASPC version are not part of the identity.
Production, validation, and development ASPCs may bind the same approved rule set when
their clinical wording is identical.

An ASPC is valid only when all of the following are true:

- `reporting.clinical_rule_set_id` names an active published rule set.
- The rule-set analyte matches the ASPC category.
- Every entry in `reporting.report_sections` has an explicit analysis declaration.
- A declaration is either `enabled`, meaning rule blocks may produce wording, or
  `none`, meaning no narrative is intentionally produced for that analysis.

There is no implicit `base` fallback. A subpanel that uses base wording binds the base
rule-set identifier explicitly.

Samples do not store `clinical_rule_set_id`. Existing and newly ingested samples resolve
their effective ASPC by assay, subpanel, and environment; the ASPC then supplies the
binding. Legacy sample documents therefore require no reporting-rule backfill. Historical
ASPC versions are migrated as well as active versions so their configuration remains
self-describing.

In **Admin > Assay Configurations**, the Clinical Rule Set control is a dropdown of active
published releases for the selected assay. Selecting an assay chooses its `base` release
by default. Selecting a subpanel chooses the exact subpanel release when one exists, or
the explicitly listed base release otherwise. All available releases for that assay stay
visible so an authorized administrator can deliberately choose another compatible
release. Save-time validation still rejects a missing, unpublished, inactive, or
analyte-incompatible selection.

## Document Model

Each collection document is one independently versioned draft or immutable release.

| Area | Purpose |
| --- | --- |
| `rule_set_id`, `scope` | Stable ASP, subpanel, analyte, and language identity. |
| `content_version` | Monotonic clinical content version within the stable identity. |
| `revision` | Optimistic-lock revision incremented by edits and lifecycle changes. |
| `status`, `active` | Workflow state; only one published version can be active. |
| `analysis_declarations` | Explicit narrative decision for each report analysis. |
| `blocks` | Ordered report sections, evaluation scope, match policy, and rules. |
| `terminology` | Approved phrase sets consumed by named deterministic renderers. |
| `test_cases` | Prepared facts and exact expected rules/text evaluated before release. |
| `review`, `lifecycle` | Submission, review, publication, retirement, actors, and reasons. |
| `content_hash` | SHA-256 hash of immutable clinical content recorded at publication. |

MongoDB enforces unique `(rule_set_id, content_version)` values and at most one active
published version for each `rule_set_id`. Publication deactivates the previous release
in one transaction. Released documents are never edited in place; create a new draft
revision from the release.

### Rule-set identity, content version, and revision

These values identify different layers of the rule-set history and must not be used
interchangeably.

| Value | Scope | Changes when | Clinical meaning |
| --- | --- | --- | --- |
| `rule_set_id` | One assay, subpanel, and language combination | Never for that scope | Stable identity, for example `hema_gmsv1__base__sv`. |
| `content_version` | One independently governed clinical content candidate or release | A new draft is created for the same `rule_set_id` | Clinical release sequence. This is the version shown as `v1`, `v2`, and so forth. |
| `revision` | One MongoDB document for one content version | The draft is saved or the document changes workflow state | Technical concurrency and mutation counter, not a clinical release number. |
| `schema_version` | The rule-document contract | The application adopts a new incompatible document format | Technical format version, not authored content history. |

A newly created scope starts with content version `1`, revision `1`. Creating a draft from
a published or rejected version allocates the next content version for the same stable
identity and resets revision to `1`. The content version remains unchanged as that document
moves through submission, clinical review, approval, publication, and retirement.

Draft auto-save sends the revision currently displayed by the editor. MongoDB updates the
draft only if that revision is still current and increments it atomically. If another editor
has already saved, the update matches no document and the API returns a conflict instead of
overwriting the newer draft. Workflow transitions also increment revision. Consequently,
revision numbers can rise frequently and can contain both content saves and status changes.
They must not appear in a report as the identity of the approved clinical content.

For example:

```text
hema_gmsv1__base__sv · content version 2 · revision 7 · draft
```

This identifies the seventh persisted state of the version 2 document. After independent
review and publication, it remains content version 2 even though publication increments its
revision. A later clinical wording change starts a separate version 3 document at revision 1.
Content-version gaps are valid because a rejected or otherwise unused draft still consumed its
version number; identifiers are never reused.

### Immutable revision history

The application preserves the following history:

| History | Preserved | Stored information |
| --- | --- | --- |
| Published, rejected, and retired content versions | Yes | The complete rule-set document remains in `clinical_rule_sets`; a later publication does not replace or delete it. |
| Current draft state | Yes | The latest complete draft document and its current revision in `clinical_rule_sets`. |
| Workflow history within a version | Yes | Append-only lifecycle entries record transition, actor, time, and reason. |
| Central rule-operation audit | Yes, when audit persistence succeeds | A non-expiring `traceability` event records action, actor, rule-set identity, content version, revision, and status. It contains metadata, not the full rule content. |
| Exact content of every persisted revision | Yes | `clinical_rule_revisions` stores the complete canonical rule-set document after creation, each draft save, every workflow transition, publication-driven deactivation, publication, and retirement. |
| Sample-backed test executions | **No** | Testing is deliberately non-persisting and currently creates no clinical test-result record. |

Each immutable snapshot contains the rule-set ObjectId, stable identity, content version,
revision, action, actor, timestamp, reason, complete document, SHA-256 revision hash, and the
previous revision hash. The unique `(rule_set_oid, revision)` index prevents duplicate revision
numbers. The previous hash forms a per-version chain, making missing, reordered, or changed
snapshots detectable during an integrity review.

The current document update and its revision snapshot are committed in the same MongoDB
transaction. If either write fails, neither state is committed. Publishing also snapshots the
automatic deactivation of the previously active release. Clinical-rule writes therefore require
a MongoDB deployment that supports transactions: a replica set or sharded cluster.

> **Important: preserve both stores**
>
> `clinical_rule_revisions` is the authoritative full-content revision archive. Lifecycle entries
> describe state changes inside a version, while `audit_events` supports cross-application event
> review and remains metadata-only. Back up `clinical_rule_sets`, `clinical_rule_revisions`,
> `reports`, `reported_variants`, and traceability audit events together. Application immutability
> does not prevent a privileged database administrator from changing MongoDB directly.

Issued-report traceability has a stronger boundary. A saved report retains the rendered text,
rule-set object identifier, stable identity, content version, schema version, content hash,
effective date, and matched rule identifiers. The corresponding published rule-set document
is retained after replacement or retirement. These values identify and integrity-check the
approved rule content used for the report.

In the admin authoring workspace, **Revision history** opens the preserved revisions for the
selected content version. An operator can select any revision and inspect its status, actor,
time, reason, hash chain, sections, rendered output composition, conditions, and exact rule
definition. History is read-only; restoring old content requires creating or editing a draft
through normal governance.

## Blocks And Rules

A block controls where and how a group of rules is evaluated.

| Field | Meaning |
| --- | --- |
| `section` | Destination report section. |
| `section_order`, `block_order` | Stable report ordering; lower values render first. |
| `analysis` | Optional report analysis gate such as `SNV`, `CNV`, or `FUSION`. |
| `evaluation.mode` | `once`, `each_finding`, or `each_item`. |
| `evaluation.collection` | Required for `each_item`; selects a prepared collection. |
| `show_heading` | Whether the flattened Markdown contains a section heading. |
| `match_strategy` | `all_matches`, `first_match`, `exactly_one`, or `at_most_one`. |

Rules within a block have a stable `rule_id`, display name, order, optional condition,
typed output sequence, rationale, and references. Rules with no condition always match.
`first_match` provides ordered fallback behavior. `exactly_one` and `at_most_one` make
ambiguous rule sets fail visibly instead of silently combining unintended wording.

## Conditions

The visual condition builder creates a typed expression tree. It supports:

- `all`: every child condition must match.
- `any`: at least one child condition must match.
- `not`: the child condition must not match.
- `predicate`: compare one registered fact with a typed value.
- `collection_match`: apply a nested condition to `any`, `none`, `all`, or a specified
  count of items in a prepared collection.

Available comparison operators depend on the fact type. They include equality,
membership, list containment/overlap, numeric comparisons, inclusive ranges, existence,
empty values, and explicit unknown values. Missing values are not converted to zero,
`false`, or an empty string. Missing data fails a condition closed and is recorded in
the evaluation trace.

The complete fact catalog is returned by `GET /api/v1/admin/clinical-rule-sets/facts` and is
the source for the UI controls. Current groups cover sample, ASP, ASPC, finding,
aggregate-result, and current collection-item facts. A new fact requires a typed
prepared-context field, registry entry, validation, UI support, and tests; rule authors
cannot address arbitrary MongoDB fields.

### Condition fields

| Field | Values | Meaning |
| --- | --- | --- |
| `type` | `predicate`, `all`, `any`, `not`, `collection_match` | Selects the typed condition node. |
| `fact` | Registered fact path | Value read from the prepared context by a predicate. |
| `operator` | Operator allowed for the selected fact type | Defines the comparison without executable expressions. |
| `value` | Typed scalar or list | Expected value; omitted only for `is_empty` and `is_unknown`. |
| `children` | One or more conditions | Child conditions for `all` and `any`. |
| `child` | One condition | Negated condition for `not`. |
| `collection` | `findings`, `biomarkers`, `applied_gene_lists`, `tier_summaries` | Prepared list inspected by `collection_match`. |
| `quantifier` | `any`, `none`, `all`, `count` | Required collection cardinality. `all` does not match an empty collection. |
| `where` | One nested condition | Condition evaluated with the current collection member exposed under `item`. |
| `count.operator` | `eq`, `ne`, `gt`, `gte`, `lt`, `lte` | Comparison used only by the `count` quantifier. |
| `count.value` | Non-negative integer | Expected number of matching collection members. |

### Operator matrix

| Operator | String/boolean | Number/integer | List | Behavior |
| --- | --- | --- | --- | --- |
| `eq`, `ne` | Yes | Yes | No | Exact typed equality or inequality. |
| `in`, `not_in` | Yes | Yes | No | Actual scalar is, or is not, a member of the configured list. |
| `gt`, `gte`, `lt`, `lte` | No | Yes | No | Numeric comparison. Type mismatch fails closed. |
| `between` | No | Yes | No | Inclusive lower and upper bounds supplied as a two-value list. |
| `contains` | No | No | Yes | Actual list contains the configured scalar. |
| `overlaps` | No | No | Yes | Actual list and configured list share at least one value. |
| `exists` | Yes | Yes | Yes | Tests path presence. A present `null` value still exists. |
| `is_unknown` | Yes | Yes | Yes | Matches explicit `null` or the canonical string `unknown`; it does not match a missing path. |
| `is_empty` | No | No | Yes | Matches an empty string, list, tuple, mapping, or set. |

### Registered variables

| Variable | Type | Evaluation scope | Meaning |
| --- | --- | --- | --- |
| `sample.asp_id` | string | all | Assay identity resolved for the sample. |
| `sample.subpanel_id` | string | all | Effective subpanel identity. |
| `sample.environment` | string | all | Effective ASPC environment. |
| `sample.omics_layer` | string | all | `dna` or `rna`. |
| `sample.analysis_intent` | string | all | `somatic` or `germline`. |
| `sample.paired` | boolean | all | Whether a control sample participates in analysis. |
| `sample.genome_build` | string | all | Prepared reference genome build; may be unknown. |
| `asp.asp_group` | string | all | Center-defined assay group. |
| `asp.asp_category` | string | all | Assay analyte category. |
| `asp.accredited` | boolean | all | ASP accreditation state. |
| `asp.germline_genes` | string list | all | Germline-capable genes declared by the ASP. |
| `aspc.reporting.report_sections` | string list | all | Analyses selected for report composition. |
| `finding.kind` | string | each finding | `snv`, `cnv`, `fusion`, or `translocation`. |
| `finding.gene` | string | each finding | Single primary gene when available. |
| `finding.genes` | string list | each finding | All prepared genes for the finding. |
| `finding.tier` | integer | each finding | Current clinical tier or unknown. |
| `finding.exon`, `finding.intron` | string list | each finding | Prepared transcript coordinates. |
| `finding.case_vaf_percent` | number (%) | each finding | Case VAF converted to percent without substituting missing values. |
| `finding.control_vaf_percent` | number (%) | each finding | Control VAF percent when available. |
| `finding.consequence` | string list | each finding | Selected transcript consequence terms. |
| `finding.hgvsc`, `finding.hgvsp` | string | each finding | Selected transcript HGVS descriptions. |
| `finding.cnv_effect` | string | each finding | Prepared gain/loss effect. |
| `finding.fusion_gene_1`, `finding.fusion_gene_2` | string | each finding | Prepared structural-event partners. |
| `aggregates.finding_count` | integer | all | Number of prepared findings. |
| `aggregates.snv_count`, `cnv_count`, `fusion_count`, `translocation_count` | integer | all | Prepared finding counts by analysis. |
| `aggregates.biomarker_count` | integer | all | Number of prepared biomarker result documents. |
| `aggregates.has_tiered_snvs` | boolean | all | Whether a Tier I-III SNV summary exists. |
| `aggregates.has_reportable_findings` | boolean | all | Whether any prepared finding or biomarker exists. |
| `item.kind`, `item.gene`, `item.genes`, `item.tier` | typed by field | each item | Current member during `collection_match` or `each_item` evaluation. |

The API fact catalog is authoritative if this table and a deployed service differ. Fields
present in internal MongoDB documents but absent from the catalog cannot be used by rules.

## Output

Rule output is an ordered sequence of typed nodes rather than executable template code.

| Node | Purpose |
| --- | --- |
| `text` | Approved literal clinical wording. |
| `fact` | A registered scalar fact with an explicit missing-value policy. |
| `list` | A registered list with controlled formatting and conjunction. |
| `number` | A registered numeric fact with precision and optional `%` or `x` unit. |
| `message` | Singular or plural text selected by a registered count. |
| `paragraph_break` | An explicit Markdown paragraph boundary. |
| `renderer` | A named, deterministic domain renderer with governed terminology. |

Named renderers are limited to the registered set (`dna_report_intro`, `tier_summary`,
and `fusion_summary`). They cannot query MongoDB, call external services, execute code,
or invent missing data. Assay-specific prose belongs in literal output or the rule-set
terminology payload, not in Python branches.

## Authoring Workspace

Users with rule permissions open **Admin > Clinical Report Rules**. The workspace keeps
scope/version selection, rule editing, and output review visible together:

1. Search or filter rule sets by workflow state.
2. Create a scoped draft by selecting an active ASP from the assay dropdown, entering the
   subpanel and language, or create a new content version from a published/rejected one. The
   analyte is derived from the ASP and cannot be entered independently. Starting creation
   clears the open release from the editor so existing content cannot be mistaken for the new
   draft. The suggested rule-set name follows the assay and subpanel until the author edits it.
3. Add report sections and ordered rules.
4. Build nested conditions using labelled facts and only compatible operators.
5. Compose report text from literal text, facts, paragraph breaks, and named summaries.
6. Review save state, validation results, clinical rationale, and change summary.
7. Submit, clinically review, publish, or retire according to assigned permissions.

Draft updates use optimistic locking. If another editor saves first, the API rejects the
stale revision so the newer content must be reloaded and reconciled. The editor cannot
modify submitted, approved, published, or retired content.

New sections and rules receive readable, collision-free names and identifiers based on their
section and order. These are starting values, not locked values: authors can edit the rule-set
name, section name and identifier, and clinical rule name and identifier while the document is
a draft. Validation still requires identifiers to be non-empty and unique across the rule set.

On wide screens, the rule-set list, report-section list, rule builder, and live text preview are
separated by keyboard-accessible draggable dividers. The browser retains adjusted widths. The
workspace fills the available viewport height and scrolls each pane independently. The rule-set
list can collapse to a narrow vertical rail. The report-section list collapses to a vertical tab
rail that retains every section as a selectable entry. Collapsed panes are removed from the grid
calculation so the builder and preview immediately use the released width.

Workflow badges use distinct semantic status tokens. Section colors are positional navigation
cues rather than clinical classifications; the selected section, its editor, and its preview use
the same cue. Condition groups use separate token-based surfaces for predicates, all/any groups,
negation, and collection matching so nested logic remains visually legible.

All authoring and lifecycle endpoints are administrative endpoints under
`/api/v1/admin/clinical-rule-sets`. They are implemented in the admin HTTP package and
remain independently protected by the operation-specific permissions below.

### Sample-backed testing

**Admin > Clinical Rule Testing** evaluates any non-retired rule-set version against an
existing sample before publication. The rule-set selector fixes the required assay and offers
two search scopes: exact assay plus subpanel, or any sample from the assay. Search results are
restricted to the operator's assigned assays and environments. Before a search is entered, the
list contains the ten most recently added compatible samples; a search returns the ten newest
matching samples using the same server-side identifier search as the sample list. Selecting a
sample does not change its filters, classifications, comments, ASPC binding, reporting state, or
files.

The preview uses the same DNA or RNA finding filters, annotations, classifications, and fact
preparation as a normal report preview. A rule-testing mode omits work that cannot affect rule
facts: report header and template assembly, display-only finding conversion, sample and finding comments,
VEP display translations, finding snapshots, and CNV profile file reads. This avoids building an
entire printable report for an interactive rule test while preserving clinical evaluation parity.
It substitutes only the explicitly selected rule-set version, evaluates the prepared live facts,
and returns the rendered report summary and rule trace. Preview segments retain their report
section color. The initial preview evaluates conditions through the normal report path and returns
the summary plus the compact matched/unmatched rule trace. Opening the execution trace makes a
second, explicit diagnostic request that adds collection-item identity, missing facts, and the
complete nested predicate/all/any/not/collection decision tree. Deferring that recursive trace
keeps the initial preview responsive for rule sets evaluated once per finding or collection item.
Detailed condition traces are not added to routine report-preview or saved-report payloads.
The operation always uses preview mode, disables finding snapshots, and never calls report
persistence. It requires
`clinical_rules:test`; ordinary rule visibility does not grant access to sample-backed testing.

## Validation And Embedded Cases

Validation checks the complete rule set before submission and again before publication:

- engine-version compatibility;
- non-empty blocks and unique block/rule identifiers and ordering;
- analysis declarations and enabled block consistency;
- condition depth, registered fact scope, and type-compatible operators;
- output fact availability and formatter contracts;
- consistent heading behavior per report section;
- every embedded test case against exact matched rule identifiers and rendered sections.

Warnings identify review gaps, such as enabled analyses without blocks or no embedded
test cases. Structural or exact-output failures block release.

Embedded cases use the same `PreparedReportContext` contract as production evaluation.
Include positive, negative, boundary, missing-value, precedence, and multi-finding cases
for each clinical behavior changed.

## Lifecycle And Permissions

The controlled lifecycle is:

```text
draft -> submitted -> in_clinical_review -> approved -> published -> retired
                                  |-> rejected
```

Rejected and published versions can seed a new draft. The latest content editor cannot
approve that version. Publication requires an independent recorded clinical reviewer.
Every transition records the actor, time, reason, rule-set identity, version, and
revision in the rule document and central audit log.

| Permission | Operations |
| --- | --- |
| `clinical_rules:view` | Read rule sets, versions, facts, provenance, and queues. |
| `clinical_rules:draft` | Create/edit drafts, validate, and preview. |
| `clinical_rules:test` | Search authorized compatible samples and run read-only sample-backed previews. |
| `clinical_rules:submit` | Submit a validated draft. |
| `clinical_rules:clinical_review` | Start review and approve or reject content. |
| `clinical_rules:publish` | Publish an independently approved version. |
| `clinical_rules:retire` | Retire an active release with a reason. |

Bundled roles separate these duties: `clinical_rule_author`,
`clinical_rule_reviewer`, and `clinical_rule_publisher`. Centers may compose equivalent
roles, but approval separation remains enforced by the service.

## Runtime Evaluation And Provenance

Report preparation creates facts only from the exact filtered findings, biomarkers,
applied gene lists, ASP, and ASPC used for that report. The service then:

1. resolves the explicit ASPC binding;
2. requires the active published release and matching analyte;
3. verifies the release content hash and engine compatibility;
4. checks all selected report sections are declared;
5. evaluates blocks in deterministic order;
6. returns rendered sections and a per-rule trace.

Saved reports retain the rendered result, rule-set object identifier, stable identity,
schema and content versions, content hash, language, effective date, and ordered matched
rule identifiers. A later rule release does not alter an issued report.

The sample-comment suggestion endpoints use this same evaluator. Suggested text and
final report text therefore have one source and one interpretation path.

## Deployment And Initial Population

Application startup verifies the `clinical_rule_sets` and `clinical_rule_revisions` indexes but does not create or
publish clinical content. Demo bootstrap loads synthetic published rules before ASPCs.
Existing deployments install the rule permissions and bundled duty-separated roles with:

```bash
PYTHONPATH=. .venv/bin/python scripts/sync_rbac_catalog.py \
  --mongo-uri "${MONGO_URI}" \
  --identity-db "${IDENTITY_DB}"
```

Before the first clinical-rule edit on an installation that already contains rule sets, capture
one immutable baseline of every current version:

```bash
PYTHONPATH=. .venv/bin/python scripts/backfill_clinical_rule_revisions.py \
  --mongo-uri "${MONGO_URI}" \
  --db coyote3_new \
  --actor reporting.migration \
  --dry-run
```

Review the count, remove `--dry-run`, and run the same command. It is idempotent and never changes
`clinical_rule_sets`. A baseline preserves the complete state that exists at execution time;
earlier overwritten draft revisions cannot be reconstructed and the command reports this limit.
New database bootstrap creates baselines for bundled demo rule sets automatically.

For a database whose approved report content is still represented by the repository's
pre-canonical rule source, run the explicit operator migration before starting the new
application version:

```bash
PYTHONPATH=. .venv/bin/python scripts/migrate_clinical_reporting_rules.py \
  --mongo-uri mongodb://localhost:27017 \
  --db coyote3_new \
  --actor reporting.migration \
  --clinical-reviewer clinical.reviewer \
  --dry-run
```

Remove `--dry-run` only after reviewing the plan. The target `clinical_rule_sets`
collection must be empty. The command reads the installed ASP catalog, ignores source
files for assays not installed at that center, and fails when an installed assay has no
source. It imports base and explicit subpanel sources, incorporates the approved
introductory wording from matching ASPCs, validates every rule set and prospective ASPC
before writing, inserts published versions with their immutable first-revision snapshots, and
binds every active and historical ASPC.
If a database write or final validation fails, both inserted rule documents and changed
ASPC reporting objects are restored. Actor and clinical reviewer must be different.

The imported source preserves the established report behavior from the previous report
generator: configured assay introduction, paired-control wording, selected gene-list and
germline scope, tiered SNV summaries, no-reportable-SNV wording, accreditation conclusion,
and RNA fusion summaries. Current source files may add scoped clinical behavior absent
from the previous generator, such as the `solid_gmsv3/endometrie` finding rules. After
cutover, the files are migration input only; MongoDB is the sole runtime source.

The previous generator also contained CNV, DNA translocation, HRD, and MSI text branches.
They are deliberately declared with `narrative: none` in the initial canonical releases.
Those branches coupled wording to legacy record shapes and embedded interpretation
thresholds, including HRD and MSI cutoffs, that are not approved clinical-rule facts in the
current contracts. Do not copy or activate them as part of migration. Introduce each one as
a reviewed new content version after its result fields, units, thresholds, exact wording,
and regression cases are approved. The underlying CNV, translocation, and biomarker report
tables remain unaffected by this narrative decision.

Apply the repository index contract before application startup:

```bash
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py apply
```

## Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/reporting/test_clinical_rules.py
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_aspc_contract_flow.py
PYTHONPATH=. .venv/bin/pytest -q tests/api/test_api_route_security.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/reporting \
  tests/unit/test_report_summary.py \
  tests/unit/test_report_summary_extended.py \
  --cov=api.application.reporting.clinical_rules \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-fail-under=100
```

The clinical reporting package has a mandatory 100% statement and branch coverage gate in
`scripts/run_family_coverage_gates.sh`. Tests cover every operator, nested condition,
collection quantifier, output node, renderer branch, lifecycle transition, authorization
boundary, malformed or missing fact behavior, integrity failure, and exact embedded case.
