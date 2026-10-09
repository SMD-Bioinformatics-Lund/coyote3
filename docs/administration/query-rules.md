# Finding query rules

## Browse rule versions

The rule list uses the same workspace controls and workflow-status badges as the
clinical report-rule editor. Search by query ID, group, assay, subpanel, analysis
or intent, and filter by workflow state or assay group. Selecting a version opens
its scope and conditions in the editor; the highlighted row identifies the current
selection. Filtering the list does not change or discard the open draft.

The **Workflow state** dropdown includes all supported query-rule states: Draft,
Approved, Published and Retired, with **All workflow states** showing every version.

On desktop, the versions list is on the left, the editor is in the center and the
effective-policy preview is on the right. Drag either divider to resize its sidebar,
or collapse the versions list for more editor space. Each panel scrolls independently.
Narrow screens stack the panels. Published and approved versions retain their
read-only behavior.

The editor header contains the change reason and permitted lifecycle actions.
**Scope and inheritance** and **Conditions** separate configuration from condition
authoring. Revision history is available in the right-hand preview sidebar.

**Test rules** opens **Query Rule Testing**, also available as an Administration
card, with `query_rules:test` permission. Select a saved version, then use
**Test with a sample** to compare findings. Save edits before opening this page;
unsaved changes are not included in its tests. Policy composition uses
`POST /api/v1/admin/query-rule-sets/preview`; sample search and execution use the
dedicated `POST /api/v1/admin/query-rule-sets/test-samples` and
`POST /api/v1/admin/query-rule-sets/test-samples/{sample_id}/preview` endpoints.

Read-only versions display their saved scope, actions and defined conditions as
cards. Field search, value-entry guidance, empty criterion inputs and editing
controls appear only while authoring a draft.

### Inspect the final MongoDB query

Open **Test rules**, select a saved version and a ready sample, then review **Final MongoDB
queries**. The two predicates show the currently published policy and the selected
version or draft applied to that sample. They are the predicates passed to the
preview repository, including sample identity, application base evidence, inherited
exceptions and resolved sample-filter values. The preview endpoint returns them as
`published_query` and `draft_query` alongside the comparison counts.

A scope-only policy preview cannot produce a final executable query: sample
filters, gene lists, VEP consequence mappings and assay configuration are required.
Individual compiled exceptions are not presented as the full query. CNV effect
selection and translocation checks that run after MongoDB retrieval are identified
separately in `post_filters`. Counts reflect those checks as well as the predicates.
Changing the scope or draft invalidates the displayed sample result; test again
to see the updated query. Query inspection uses the existing sample-test permission
and sample-access checks.

Query rules control finding retrieval for an assay group, an assay within that group,
or a subpanel associated with that assay. Open **Administration → Query rules** to
inspect the effective policy, prepare a draft and publish an approved version.
Reporting rules remain separate: query rules select findings; reporting rules evaluate
clinical facts and generate report text.

## Scope and inheritance

Policies resolve in this order:

1. Application-owned base query.
2. Published **Default: all groups** policy for the analysis and intent.
3. Published policy for the assay group.
4. Published policy for that group and assay (ASP).
5. Published policy for that group, assay and subpanel.

Each policy belongs to one analysis: SNV, CNV, DNA translocation or RNA fusion.
SNV policies distinguish somatic and germline intent for authoring and inheritance.
The current combined SNV workflow also applies germline exceptions during somatic
retrieval, as described below. Policies for other analyses remain independent. A subpanel policy always includes its assay;
sharing a subpanel identifier across assays does not share a query policy.

!!! warning "Somatic queries can return germline variants"

    Intent scopes select query policies, not confirmed variant origin. Current
    somatic SNV queries can include germline variants that meet their criteria.
    The dedicated germline SNV pathway is not yet fully implemented. Published
    germline exceptions are therefore evaluated within somatic SNV retrieval for
    the same group, assay and subpanel. The somatic evidence mode remains active;
    the germline evidence mode does not replace it. Germline policy options do not
    imply a complete germline workflow or biological separation of the results.

The resolver composes each intent's hierarchy independently, then adds the effective
germline exceptions to the somatic exceptions. Effective germline identifiers use a
`germline__` prefix in the combined preview; stored rule IDs are unchanged. The
preview includes their source versions. Somatic replacement mode replaces only the
somatic list; edit the germline scope to change its contribution.

Admission exceptions provide an alternative to ordinary evidence and consequence
requirements. Gene/position restrictions and sample identity remain enforced.
Exclusions apply after admission and can remove a finding admitted by either intent.
`extend_consequence` preserves ordinary evidence requirements. Retired, draft and
unpublished germline rules do not affect live selection. Sample tests for germline
drafts compare their effect on somatic SNV results using the sample's somatic filters;
the sample does not need the germline intent enabled.

| Setting at a scope | Effective behavior |
| --- | --- |
| No published version | Continue with the parent policy. |
| Evidence mode set to **Inherit parent** | Keep the parent's evidence mode. |
| Exception list set to **Inherit parent exceptions** | Keep the parent's complete list. |
| Exception list set to **Inherit and add exceptions** | Retain the parent list and append this scope's additional exceptions. Inherited rules remain read-only. |
| Exception list set to **Replace inherited exceptions** | Use this scope's complete list instead of the parent list. |
| An explicitly empty replacement list | Clear inherited exceptions; retain ordinary base-query behavior. |
| Retired version | Ignore that version and resolve from remaining published ancestors. |

For example, a group can use case-only SNV evidence. An assay can replace its
exceptions while inheriting case-only evidence. A subpanel can then select paired
evidence while retaining the assay's exception list. A change to a parent immediately
affects descendants that inherit the changed field.

The application base defines supported predicates and default evidence modes. The
[application-owned query seed](../configuration/clinical-query-policy-file.md) is
loaded by Python bootstrap tools into database rules. It is not part of the editable
center bundle. Use the editor to publish changes to installed policies.

## Prerequisites

- For a group-specific policy, register an active [assay group](assay-groups.md).
  The **Default: all groups** scope does not require a group or assay.
- For assay scope, register an active ASP belonging to that group.
- For subpanel scope, create an active subpanel definition and associate it with the ASP.
  `base` means no specific subpanel; it is not a separate subpanel scope.
- Complete the assay's [ASPC and gene-list configuration](assay-setup.md). Query rules
  do not create analysis availability, gene lists or missing finding data.
- Assign the permissions below to the author, reviewer and publisher. The reviewer
  must differ from both the draft creator and its most recent editor.

| Permission | Operation |
| --- | --- |
| `query_rules:view` | List versions, inspect registered scopes and preview policy resolution. |
| `query_rules:draft` | Create versions and edit drafts. |
| `query_rules:review` | Approve a draft after independent review. |
| `query_rules:publish` | Activate an approved version. |
| `query_rules:retire` | Retire a published version and restore inheritance. |
| `query_rules:test` | Compare published and proposed selection on authorized ready samples. |

The installer provides these protected roles. Assign multiple roles when one account
needs several responsibilities; independent review still requires another account.

| System role | Grants |
| --- | --- |
| `query_rule_viewer` | View and preview. |
| `query_rule_author` | View, create and modify drafts. |
| `query_rule_reviewer` | View and independently approve drafts. |
| `query_rule_publisher` | View, publish approved versions and retire publications. |
| `query_rule_tester` | View policies and run read-only sample comparisons within assigned assay/environment access. |

These roles grant no sample access or reporting-rule permissions. See the
[system role catalog](system-role-catalog.md) for all installed roles and exact grants.

## Create and activate a policy

### Generated identities

Each document defines one analysis and intent. `query_id`, `scope_key` and the stored
name use `assay_group__assay__subpanel__intent_datatype`; operators cannot edit them.

| Scope | Example identity |
| --- | --- |
| Shared default | `default__all__base__somatic_snvs` |
| Assay group | `hematology__all__base__somatic_snvs` |
| Assay | `hematology__example_panel__base__somatic_snvs` |
| Named subpanel | `hematology__example_panel__myeloid__somatic_snvs` |
| CNV rules for an assay | `hematology__example_panel__base__somatic_cnvs` |

The supported data-type suffixes are `snvs`, `cnvs`, `fusions` and `translocations`.
Only SNVs currently support the `germline` intent. `default` as a group token,
`all` as an assay token and the `__` separator are reserved. `base` means no
specific subpanel and normalizes to null in the stored query scope. Samples may
still carry `base` as their no-subpanel identifier.

Retrieval selects published IDs for the shared default, group, assay and optional
named subpanel, in that order. It resolves inheritance before building and executing
the sample-scoped query. No separate base-subpanel rule is evaluated.

### Existing query-rule storage

Stop query-rule editing during the storage upgrade. Run
`scripts/database/upgrade_query_rule_storage.py --env-file "$COYOTE_ENV_FILE" --mongo-uri "$MONGO_URI" --db "$COYOTE3_DB" --actor "$OPERATOR"`
to validate and inspect the plan. Apply the same command with
`--apply --backup /private/backup/query-rules.json`; the backup path must not exist.
The script preserves conditions, release versions and lifecycle states, updates
generated identities, increments changed document revisions and records immutable
baselines and an audit receipt in one transaction. It never reconstructs past edits.
Deploy matching API and worker code with the upgraded storage.
The environment file supplies identity-database settings for transactional audit
routing; the explicit URI and database arguments select the migration target.

If old assay-wide and base-specific versions collapse to a duplicate version or
publication, the upgrade stops for explicit resolution. Existing immutable history
is never rewritten automatically. A second run with no remaining changes is a no-op.

### Revision history and lifecycle

Rule versions are stored in `query_rule_sets`; immutable, hash-linked snapshots are
stored in `query_rule_revisions`. Creation, edits, approval, publication, supersession
and retirement capture a revision in the same transaction as the version and audit
receipt. **Revision history** displays and verifies the saved snapshots.

An editor with `query_rules:draft` can enter a reason and select **Delete draft**.
Deletion removes only the inspected draft and its private snapshots, with an audit
receipt retained. Stale revisions, approved versions, published versions and retired
versions cannot be deleted. Withdraw a publication with **Retire** instead.

For installations without query-rule snapshots, `scripts/bootstrap/install_query_rules.py`
plans missing baselines by default and captures them with `--apply`. Baselines preserve
the current retained versions; they do not reconstruct earlier edits. First-install
bootstrap captures the installed versions automatically.

1. Select **New scope version**. The query ID and stored name are generated from the scope.
2. Select the analysis and, for SNV, the intent.
3. Select **Default: all groups** for a shared default, or select a group.
   Leave **All assays in group** for a group policy; select an
   assay to narrow it. Leave **All subpanels in assay** or select an associated subpanel.
4. In **Conditions**, select **Add condition** to open the field and operator editor.
   When the list is inherited, adding a condition selects **Inherit and add exceptions**.
   No parent conditions or sample filter values are copied. Each exception
   needs a unique identifier, an action and at least one match condition. Use nested
   logical groups for combinations of conditions within the same exception.
5. Select **Preview effective policy**. Compare **Currently published** with
   **Draft result**. The ordered source list identifies inherited versions and fields.
6. Enter a change reason and select **Save draft**. Drafts do not affect live retrieval.
7. Have an independent reviewer open the saved version, preview it, enter a review
   reason and select **Approve**. Validate representative synthetic samples in a
   testing deployment before production publication.
8. A publisher enters the activation reason and selects **Publish**. Confirmation
   identifies the effect on this scope and inheriting children.

Approved and published content cannot be edited. Use **Copy to new draft version**
to prepare a successor. Publishing it retires the previous publication at the exact
same scope in one transaction. Historical versions remain available. To withdraw
a publication, enter a reason and select **Retire**; this restores parent inheritance,
not an older publication at the same scope.

Each write checks the version's current revision. A conflict requires refreshing and
reviewing the latest state before retrying. Creation and lifecycle changes are recorded
through the transactional audit outbox. MongoDB must support transactions.

## Supported settings

| Setting | Meaning |
| --- | --- |
| SNV `paired` | Require a genotype labelled `case` meeting the sample's allele-frequency, depth and alternate-read thresholds. If control genotypes exist, at least one must meet the maximum control frequency and minimum depth. Records without a control genotype remain eligible. Population-frequency and consequence filters also apply. |
| SNV `case_only` | Accept a genotype meeting the sample's case allele-frequency, depth and alternate-read thresholds without requiring a role label. This branch does not restrict the genotype's role or apply the control evidence check. Population-frequency and consequence filters also apply. |
| SNV `exception_only` | Suppress the ordinary evidence branch; matching `admit` exceptions can admit findings. An empty list admits no findings. |
| `admit` | Add findings matching typed criteria within the sample's mandatory identity boundary. Admission can bypass ordinary evidence filters; review its scope carefully. |
| `exclude` | Remove findings matching typed criteria, including otherwise admitted findings. |
| SNV `extend_consequence` | Extend eligible consequences while preserving the base evidence requirements. |

Evidence modes select query behavior; they do not create case/control relationships
or establish whether a finding is somatic or germline. Admission and exclusion
exceptions can modify the resulting selection as described above.

**Inherit parent** resolves each setting independently from the nearest published
ancestor: assay, assay group, shared default, then the application default. A group
scope has no assay parent. **Preview effective policy** identifies the sources used.
An inherited exception list has no local condition tree to edit; **Add condition**
starts a local extension. An empty extension retains the parent list; an empty
replacement list removes it. The API stores this choice in `content.exception_mode`
(`extend` or `replace`). A missing mode means `replace`, preserving existing saved
versions; null `exceptions` always inherits regardless of mode. No database rewrite
is required for existing versions.

An extension must not reuse an inherited identifier. To refine an existing rule,
choose **Replace inherited exceptions** and author the complete desired list,
including the refined rule. Only that local version of the rule executes at this
scope. In extension mode, both parent and local rules execute; local exclusions
remove matching findings even if a parent rule admitted them. Adding an admission
rule broadens selection rather than narrowing a parent's admission condition.
Nested conditions are never merged implicitly.

**Parent rules · read-only** shows the inherited evidence setting and every inherited
exception. **Draft result** shows the complete composed exception list and evidence
setting, not only local changes. Ordered source versions identify the composition
path. Sample testing evaluates this composition through the same runtime resolver.
Publishing a parent validates currently published descendant compositions and rejects
duplicate inherited identifiers. Parent changes still require descendant sample testing.

The assay dropdown lists active assays in the selected group and analysis category.
**All assays in group** applies the policy throughout that group. Selecting an assay
enables its active named subpanels; **All subpanels in assay** uses the `base` identifier and applies
throughout that assay. More-specific published policies can override inherited
settings. Changing the group clears the assay and subpanel selections; changing the
assay clears the subpanel selection. Saved versions have an immutable scope; select
**New scope version** to configure a different scope.

## Nested condition builder

Each exception can contain a condition tree, additional field criteria, or both.
Choose **Field condition**, then select a registered field, operator and value.
The field selector shows the stored type; the operator selector lists only
supported operators for that field. The
[field catalog](../reference/query-condition-fields.md) lists every available
path and operator for SNV, CNV, translocation and fusion records.

Use **Search stored field names** to narrow the field selector. Fields come from
the corresponding finding contract: SNV annotation and genotype fields, CNV
coordinates and gene annotations, translocation annotations, and fusion caller
evidence. Numeric-looking values stored as text, such as
`INFO.selected_CSQ.CADD_PHRED`, retain text semantics. Sample identifiers, arbitrary
untyped metadata, and mixed-type review flags are not authoring fields.

### Selecting condition values

Choose **Sample filter reference** to use the current sample's filter value, or
**Enter manually** to store an explicit literal. References store only the source
and key. The editor does not copy gene-list members, consequence groups, caller
selections or thresholds into a rule.

| Analysis | Reference keys | Runtime meaning |
| --- | --- | --- |
| SNV | `snvlists`, `vep_consequences` | Effective genes and expanded consequence terms for the active SNV intent. |
| SNV | `min_depth`, `min_alt_reads`, `min_freq`, `max_freq`, `max_popfreq` | Current read-support and frequency thresholds. |
| CNV | `cnvlists`, `min_cnv_size`, `max_cnv_size`, `cnv_loss_cutoff`, `cnv_gain_cutoff` | Effective genes and current size/ratio thresholds. |
| Translocation | `fusionlists` | Effective translocation gene selection. |
| RNA fusion | `fusionlists`, `fusion_callers`, `fusion_effects`, `fusion_descriptions`, `min_spanning_reads`, `min_spanning_pairs` | Effective genes and normalized caller, annotation and support filters. |

The active profile is `sample.filters.<intent>.<analysis>`, with the application's
existing ASPC/default inheritance. Gene references use the same gene-scope resolver
as clinical retrieval: selected ISGLs, applicable ad-hoc genes and physical assay
coverage contribute according to the established filter semantics. Gene-list IDs
are not compared directly with finding gene symbols. SNV consequence-group keys
resolve through the sample's VEP version. These resolutions occur during execution;
the rule retains its reference.

For example, this condition compares a genotype depth with the current sample's
minimum depth:

```json
{
  "type": "predicate",
  "field": "GT.DP",
  "operator": "gte",
  "value": { "source": "sample.filters", "key": "min_depth" }
}
```

The field selector offers only compatible references for that analysis and stored
field. List references support membership operators; numeric references support
numeric comparisons. An unavailable required context raises an error. No literal
fallback or copied value is used. Empty referenced lists retain MongoDB semantics:
`$in: []` and `$all: []` match nothing; `$nin: []` excludes no values. Do not assume
an empty list means an unrestricted condition.

Manually entered genes accept commas or new lines, with duplicates removed and
case preserved. Numeric lists and reference-capable list fields also accept commas.
Other text lists use one entry per line; scalar text and regular expressions are
never split. Manual lists allow up to 100 values; resolved references allow up to
100,000 values and are never truncated.

Changes to a sample's filters or the lists resolved by those filters can change a
reference's result without editing the rule. Use **Test with a sample** to evaluate
references. Policy-only preview retains symbolic references; synthetic JSON tests
are available for literal conditions only.

SNV `genes` matches the aggregated gene array; `INFO.selected_CSQ.SYMBOL` targets the
selected transcript's gene. Fusion `gene1` and `gene2` are individual partners;
`genes` is a combined stored string. For CNVs, use `genes.gene` and same-array-element
matching when combining a gene with its annotation criteria.

### Combining conditions

| Logic | Matching behavior | MongoDB predicate |
| --- | --- | --- |
| AND — match all | Every child must match. | `$and` |
| OR — match any | At least one child must match. | `$or` |
| NOR — match none | No child may match. | `$nor` |
| NOT — invert condition | Negate one condition or complete group, including its missing-field behavior. | Single-child `$nor`. |
| Match the same array element | Conditions inside the block must match one element of the selected object array. | `$elemMatch` |

Groups can be collapsed, and children duplicated, removed or reordered. Each group
must retain at least one child. Reordering does not change logical semantics.

Ordering is not precedence: reordering siblings within AND, OR or NOR, or reordering
exception entries, leaves the matched findings unchanged. Moving a condition between
groups, changing the logical operator, or adding/removing a condition can change the
result. Exclusions still remove otherwise admitted findings. A more specific scope
in replacement mode replaces its parent's list; extension mode retains it and adds
the local exceptions.

Installed predicates use the same condition-tree format as the visual editor. The
registered SNV fields include the retained VCF INFO keys `INFO.SVTYPE` and
`INFO.MYELOID_GERMLINE` used by installed policies. Missing keys are not populated by
the rules. The installed FLT3 insertion pattern matches 10–200 consecutive ASCII word
characters in `ALT`; it is an unanchored match, not a total-length constraint.
Each exception allows at most eight levels and 100 nodes; value lists allow at
most 100 entries. The API enforces these limits for UI and direct API requests.

### Operators and values

| Operators | Accepted values and meaning |
| --- | --- |
| `$eq`, `$ne` | A scalar matching the field type. **Compare with null** selects JSON null rather than the text `"null"`. |
| `$gt`, `$gte`, `$lt`, `$lte` | Numeric fields only; JSON numbers, with whole numbers required for integer fields. |
| `$in`, `$nin` | A nonempty list of correctly typed scalar values, entered one per line. Text remains case-sensitive. |
| `$exists` | Boolean `true` or `false`. A field containing null still exists. |
| `$type` | One BSON type selected from the server-provided list; no value conversion occurs. |
| `$regex` | A case-sensitive pattern on text or string-list elements, at most 200 characters. The portable grammar accepts literals, anchors, explicit character classes and unquantified groups. Shorthand classes, backreferences, lookarounds, inline flags and repeated groups are rejected; at most one unbounded quantifier is allowed. Patterns can still be expensive on large datasets. |
| `$all` | A nonempty list of text values that must all occur in a string array. |
| `$size` | A nonnegative integer: the exact length of a string or object array. |
| `$mod` | Two integers on separate lines: nonzero divisor followed by remainder. Numeric fields only. |
| `$bitsAllSet`, `$bitsAnySet`, `$bitsAllClear`, `$bitsAnyClear` | Integer fields only; 1–64 bit positions, each between 0 and 63. |

The API does not silently convert numeric strings. Integer fields reject fractions
and booleans. Comparison values cannot contain dictionaries or MongoDB expressions.
The field catalog excludes sample identity and access-control fields.

!!! important "Missing fields, nulls and arrays"

    Equality with null matches null or absent fields. Inequality with null selects
    present, non-null values. Negative predicates such as `$nin` or NOT can match
    absent fields; combine them with `$exists: true` when presence is required.
    Separate dotted-field predicates can match different array elements. Use
    **Match the same array element** when genotype or caller evidence must belong
    to the same entry.

For example, one RNA `calls` element can require a particular `calls.caller` and
minimum `calls.spanreads`. Another caller's read count cannot satisfy that block.
The same principle applies to SNV `GT` entries and translocation `INFO.ANN` entries.

The builder supports the listed finding-selection predicates. It does not accept
aggregation pipelines, `$expr`, server-side JavaScript (`$where`), geospatial or
full-text searches, cross-collection joins or write operations. These require
separate application implementations. See MongoDB's
[query predicate reference](https://www.mongodb.com/docs/manual/reference/mql/query-predicates/)
for native operator semantics.

### Additional criteria and inheritance

Within an exception, additional match fields are combined with **AND**. A condition
tree, when present, is also combined with those fields using AND. Existing published
rules retain their flat criteria and do not require conversion. Multiple
values in a field normally match **any** listed value. Exact INFO comparisons require
all named fields to equal their typed scalar values. The detailed
[exception grammar](../configuration/clinical-query-policy-file.md) specifies each
analysis's match fields, gene-pair syntax and evaluation order. The editor uses this
same grammar alongside condition trees, without accepting arbitrary database queries.
Replacement replaces the complete exception list, including its condition trees.
Extension retains parent entries and adds local entries; individual nested nodes
do not merge across scopes.

### Test with stored samples

1. Open a saved rule version or prepare a draft, including any unsaved changes.
2. Under **Test with a sample**, enter a sample name or identifier and select
   **Find samples**. Results contain ready samples in the policy's assay scope and
   the operator's assigned assay/environment scope.
3. Select **Test** beside a sample. The sample must enable the requested analysis
   and intent in its recorded configuration.
4. Compare the published and draft counts, added findings, removed findings and
   unchanged count. Expand **Effective draft inheritance** to see which policies
   apply. A more-specific published child can override the draft's fields.
5. Repeat with representative samples before review and publication.

The comparison uses the sample's recorded ASPC, saved filter values, selected gene
lists, VEP version and application query builders. It includes CNV effect filtering
and translocation gene filtering. Counts describe retrieval selection before browser
text search, classification enrichment and report eligibility; they are not report
finding counts. The proposed policy is applied at its actual hierarchy level, so
testing a group rule does not bypass an assay or subpanel override.

Tests do not save sample filters, findings, reports or rules. Results are hidden when
the draft changes. Comparisons read current data; rerun if samples, lists or published
policies change during testing. Each candidate query has a five-second server limit.
More than 10,000 candidates in either query rejects the comparison instead of
reporting partial counts. Counts are exact for completed comparisons; the display
shows at most 100 added and 100 removed finding identities.

Sample testing requires `query_rules:test`; assign the `query_rule_tester` role
alongside author or reviewer roles as appropriate. Role grants do not bypass sample
access, readiness or analysis checks.

### Policy preview and synthetic examples

**Preview effective policy** validates the draft and resolves inherited settings.
It shows readable condition expressions and expandable compiled predicates. These
are the condition-tree predicates, not the complete sample query: additional field
criteria, action semantics, base evidence and sample boundaries still apply.

Under **Advanced: synthetic condition examples**, open **Test condition with synthetic examples**, select an exception and enter
1–50 JSON objects in an array. Results identify matching examples. Testing reads
no stored records and saves no examples. It evaluates only the selected tree,
not additional criteria, admission/exclusion actions, base evidence or sample access.
Synthetic JSON cannot represent every BSON type or reproduce server query planning
and index performance. Validate representative records in an
isolated deployment before clinical publication.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/admin/query-rule-sets/options` | Registered scopes and field/operator catalog under `conditions`. |
| `POST /api/v1/admin/query-rule-sets/preview` | Effective policy, lineage and compiled condition predicates. |
| `POST /api/v1/admin/query-rule-sets/test-condition` | Analysis, condition and supplied documents; returns `matches` and `predicate`. Requires `query_rules:view`. |
| `POST /api/v1/admin/query-rule-sets/test-samples` | Scope, search and page; returns accessible ready samples. Requires `query_rules:test`. |
| `POST /api/v1/admin/query-rule-sets/test-samples/{sample_id}/preview` | Scope and optional draft content; compares published and proposed selection on the authorized sample. Requires `query_rules:test`. |

Trees are stored under each exception's `condition` key. This SNV syntax example
is not a recommended clinical threshold:

```json
{
  "id": "review_selected_genotypes",
  "mode": "exclude",
  "condition": {
    "type": "all",
    "children": [
      {"type": "predicate", "field": "CHROM", "operator": "in", "value": ["1", "2"]},
      {
        "type": "elem_match",
        "field": "GT",
        "condition": {
          "type": "all",
          "children": [
            {"type": "predicate", "field": "GT.type", "operator": "eq", "value": "case"},
            {"type": "predicate", "field": "GT.DP", "operator": "lt", "value": 20}
          ]
        }
      }
    ]
  }
}
```

The existing author, reviewer and publisher permissions govern condition trees.
Published versions and audit records retain the complete authored tree. Drafts
and synthetic tests do not change live retrieval.

## Runtime boundaries

Published policies apply to SNV and CNV lists, DNA translocation lists and RNA fusion
lists, including exports that use those retrieval workflows. DNA report preparation
uses the same SNV policy and translocation gene-scope policy. Manually selected CNV
and RNA fusion report findings retain their existing reporting eligibility rules;
query publication does not undo review decisions or rewrite saved reports.

Sample identity, access checks, finding identity and the supported query implementation
remain application-owned. Query rules cannot grant sample access, introduce an analysis
type or implement a new caller parser. HRD, MSI, TMB, coverage and PGX have no editor
namespace. The preview resolves policy settings; it does not count findings or certify
clinical suitability. Saved reports do not contain a query-policy lineage snapshot.

## Installation and storage

The [installed-defaults reference](installed-defaults.md#finding-query-sets) lists
every shipped set ID, its group scope, exact predicates and effect on retrieval.

The first-installation index-management step creates indexes for `query_rule_sets`.
Application startup verifies the index contract; it does not create missing indexes.
Bootstrap installs published version-one policies attributed to the initial administrator.
Their `system_installed` flag records origin; successors use the normal draft, review
and publication workflow. Installation is not evidence of clinical validation.

| Scope | Intent | Installed criteria |
| --- | --- | --- |
| Hematology, myeloid and tumor WGS (`tumwgs`) | Somatic SNV | Paired evidence; extend eligible consequences for FLT3 with `SVTYPE` present or ALT matching `[A-Za-z0-9_]{10,200}`. |
| Solid | Somatic SNV | Paired evidence; TERT/NFKBIE regulatory-region and TF-binding consequences. |
| Hematology, myeloid and tumor WGS (`tumwgs`) | Germline SNV | Admission by `MYELOID_GERMLINE = 1`, CEBPA with `GERMLINE` filter, or chromosome 1 positions 115256521–115256537 inclusive. These exceptions also contribute to somatic SNV retrieval in these groups. |
| Solid | Germline SNV | Admission of findings with the `GERMLINE` filter; the myeloid admissions do not apply. |

These admissions are not global defaults. Lymphoid, WTS, fusion, demo and newly registered
groups do not inherit them automatically. The legacy `master` implementation also
applied the myeloid admissions to `unknown`; that is not a registered installation
group in the current application.

The release catalog supplies group rules; the bundled installation TOML supplies the
group-scoped germline criteria and overlapping group criteria. At installation, a file
exception with the same ID replaces that catalog exception. Global file criteria are
included in installed group replacement lists. Subsequent publications use the normal
inherit, extend or replace behavior; changing a default does not change replacement child lists.
CNV, translocation and RNA fusion use application defaults unless installation input
or an administrator supplies additional rules. Validate every relevant scope before use.

Existing deployments can plan missing scopes without writing:

```bash
coyote_compose run --rm api python scripts/bootstrap/install_query_rules.py --actor ADMIN_USERNAME
```

After reviewing the plan, repeat with `--apply`. This uses the configured application
database and bundled application seed; `--db` and `--mongo-uri` allow explicit
database selection. There is no seed-file override. It never replaces an existing scope, even when all its versions are retired.
Registered assay groups must exist first. Assay/subpanel-specific file exceptions are
rejected; configure those scopes in the editor after their registries are available.
Use the `coyote_compose` helper from the [upgrade guide](../deployment/application-upgrades.md).

The first-install RBAC bootstrap includes six permissions and five dedicated roles. Existing deployments
must follow the [upgrade RBAC and index synchronization steps](../deployment/application-upgrades.md)
and assign permissions before using the editor. In particular, both scope/version
uniqueness and the single-publication index must be present before authoring.

The API resource is `/api/v1/admin/query-rule-sets`. It provides listing, scope options,
preview, draft creation and updates, and explicit approve/publish/retire operations.
Use these endpoints for policy changes; generic collection ingest does not expose this
collection. The [collection contract](../reference/mongodb-collections.md) describes
stored scope, content, version, revision, lifecycle and attribution fields.
