# Clinical Reporting Rules

Coyote3 uses repository-authored YAML rules to generate deterministic clinical
report text from findings that have already passed the analytical reporting
workflow. This guide defines the authoring format, runtime data contract,
publication process, evaluation order, provenance model, and validation
requirements.

The rules engine is a text-generation component. It does not decide which
findings pass filters and does not replace clinical classification.

!!! info
    YAML is the only editable source of a clinical rule. MongoDB stores an
    immutable compiled release so all API instances evaluate identical content
    and saved reports remain reproducible after the repository changes.

## 1. System Boundary

The reporting workflow completes these operations before invoking the engine:

1. Resolve the sample's exact ASP and ASPC.
2. Load current sample filters.
3. Resolve selected ISGLs and effective genes.
4. Query the configured analysis collections.
5. Apply analytical thresholds and gene scope.
6. Remove false-positive, irrelevant, blacklisted, and non-reportable states.
7. Resolve selected transcripts and current classifications.
8. Build normalized reportable SNVs, CNVs, fusions, translocations, and
   biomarkers from the same result sets used by the preview.
9. Create a read-only `PreparedReportContext`.

The engine receives that context and the immutable release referenced by the
ASPC. It performs no database query and no mutation.

This ordering is important. The rule engine does not receive all findings
that were ingested for a sample. It receives the final report candidates after
the ordinary analytical query, gene-list scope, exclusion state, and
classification rules have run. A rule therefore explains or combines the
reportable result; it does not make a hidden second decision about eligibility.

The engine can:

- test approved facts;
- select ordered text rules;
- render approved values into text;
- group text by report section;
- return a complete evaluation trace.

The engine cannot:

- parse source VCF, CNV, fusion, or biomarker files;
- apply analytical filters;
- choose transcripts;
- normalize gene identity;
- classify or tier findings;
- call external knowledgebases;
- infer missing clinical states;
- change sample, finding, ASP, ASPC, or report documents.

!!! caution
    A human label in a spreadsheet is not automatically a machine fact. A rule
    can use a concept only after the application provides a typed, validated
    fact with defined units and missing-value behavior.

## 2. Source And Runtime Storage

### 2.1 Authored source

Clinical rules are authored under:

```text
clinical_reporting_rules/
  master_dna.draft.yaml
  old_coyote_dna.draft.yaml
  old_coyote_rna.draft.yaml
  endometrial_dna.draft.yaml
```

The YAML file is reviewed through normal source control. Its rule IDs, criteria,
wording, examples, and version are part of the clinical change.

The source files have distinct authorities:

| Source | Authority | Intended scope |
|---|---|---|
| `master_dna.draft.yaml` | Current Coyote `master` implementation | Hematology/current DNA behavior |
| `old_coyote_dna.draft.yaml` | Archived pre-migration Python implementation | Established DNA assays not represented by current hematology logic |
| `old_coyote_rna.draft.yaml` | Archived pre-migration Python implementation | Established RNA assay summaries |
| `endometrial_dna.draft.yaml` | Endometrial clinical workbook | New endometrial conditions and wording |

All four files are drafts. This is intentional: exact source clauses are
present, but a rule set is not clinically complete until every report section
has typed facts and byte-for-byte golden cases. No draft is selected at
runtime by filename.

### 2.2 Published release

The `clinical_rule_sets` collection stores immutable compiled releases. A
release contains:

| Field | Meaning |
|---|---|
| `_id` | Immutable release identity |
| `rule_set_id` | Stable logical rule-set name |
| `version` | Author-assigned release version |
| `content_hash` | SHA-256 of canonical validated content |
| `source_path` | Repository source path used at publication |
| `source` | Complete validated rule source |
| `status` | Runtime lifecycle state |
| `published_by` | Publishing actor |
| `published_on` | UTC publication timestamp |

The unique keys are `(rule_set_id, version)` and `content_hash`.

Publishing identical canonical content is idempotent. Reusing an existing
rule-set/version for different content is rejected; the author must increment
the version.

### 2.3 Why runtime storage is required

Source control answers which rules were authored. The immutable database
release answers which exact content a running clinical deployment used.

The release provides:

- consistent behavior across API workers and containers;
- no runtime dependency on a checked-out repository path;
- exact ASPC binding;
- stable report provenance after branch history moves;
- a database identity suitable for audit and backup;
- deterministic rollback by rotating configuration to an approved release.

MongoDB is not a second authoring interface. Published content is never edited
in place.

## 3. ASPC Binding

An ASPC reporting block can bind one release:

```yaml
reporting:
  clinical_rule_release:
    release_id: "<MongoDB ObjectId>"
    rule_set_id: master_dna_reporting
    version: 1.0.0
    content_hash: 64-character-sha256
```

At runtime, Coyote3 resolves `release_id` and verifies all three identity
fields. A mismatch blocks report generation.

Changing a rule binding is a configuration change:

1. Publish the new YAML version.
2. Bind the new immutable release through the ASPC rule-release endpoint.
3. Coyote3 verifies release state and scope, retires the active ASPC document,
   and inserts the next active ASPC version with the reference.
4. Validate preview output with approved fixtures.
5. Activate the ASPC through the normal governance workflow.

Existing retired ASPCs and saved reports continue to reference their original
release.

An ASPC without `clinical_rule_release` retains the existing configured report
behavior. Coyote3 does not select a rule set by filename, assay-group guess, or
latest database version.

## 4. YAML Contract

Every source has three top-level keys in this order:

```yaml
schema_version: 2
rule_set: {}
rules: []
```

### 4.1 Rule-set metadata

```yaml
rule_set:
  rule_set_id: master_dna_reporting
  version: "0.1.0-draft"
  title: Current Coyote DNA reporting wording
  status: draft
  language: sv
  scope:
    analyte: dna
    assay_ids: []
    assay_groups: []
    subpanel_ids: []
    environments: []
  provenance:
    authority: coyote_master
    reference: coyote/blueprints/common/util.py
    revision: <full-git-commit>
    content_sha256: <sha256-of-authoritative-source>
    text_policy: verbatim
  validation:
    approval_status: pending
    approval_reference:
    golden_case_ids:
      - master-dna-no-snv
  required_facts:
    - aggregates.snv_count
  notes: Optional author guidance.
```

| Key | Rule |
|---|---|
| `rule_set_id` | Stable logical identifier; do not encode a content hash |
| `version` | Increment whenever executable criteria or wording changes |
| `status` | `draft`, `active`, or `retired`; only `active` publishes |
| `language` | Language of rendered clinical text |
| `scope.analyte` | Required; `dna` or `rna` |
| Scope lists | Empty means unrestricted for that dimension |
| `provenance.authority` | `coyote_master`, `old_coyote`, or `clinical_workbook` |
| `provenance.reference` | Exact source file or workbook used for transcription |
| `provenance.revision` | Immutable Git revision or controlled source revision |
| `provenance.content_sha256` | SHA-256 of the authoritative source artifact |
| `provenance.text_policy` | Must be `verbatim`; clinical prose is not paraphrased |
| `validation.approval_status` | `pending`, `inherited`, or `approved` |
| `validation.approval_reference` | Review record or inherited validated-system reference |
| `validation.golden_case_ids` | Exact-output cases required before publication |
| `required_facts` | Missing values block evaluation before any rule runs |

Scope is validated against the prepared sample and ASPC. A release for another
analyte, assay, group, subpanel, or environment cannot run accidentally.

An `active` source is rejected by the Pydantic contract unless it has
`inherited` or `approved` status, a non-empty approval reference, and at least
one golden case. The publisher repeats these checks at its trust boundary.

### 4.2 Rules

```yaml
- rule_id: dna_tier_1_finding
  family: finding_text
  section: Kliniskt relevanta fynd
  priority: 100
  description: Summarize one reportable Tier I small variant.
  source_locator: coyote/blueprints/common/util.py:646-688
  when:
    - fact: finding.kind
      operator: eq
      value: snv
    - fact: finding.tier
      operator: eq
      value: 1
  template: |-
    <verbatim source wording>
  heading: true
  stop: true
```

| Key | Meaning |
|---|---|
| `rule_id` | Unique stable identifier used in trace and report provenance |
| `family` | Evaluation phase |
| `section` | Rendered report section |
| `priority` | Lower values evaluate first within a family |
| `description` | Clinical intent in author-readable language |
| `source_locator` | Function/line, workbook sheet/cell, or controlled source section |
| `when` | AND-combined typed conditions |
| `template` | Verbatim clinical text with only variable placeholders substituted |
| `heading` | Whether the report composer emits `## <section>` before this section |
| `stop` | Stop lower-priority rules for the current evaluation candidate |

Rule IDs cannot repeat. Priorities cannot repeat within one family. These
constraints make ordering visible and deterministic.

Use YAML literal blocks (`|-`) for clinical prose. Folded blocks (`>`) alter
newlines and are unsuitable for byte-for-byte output verification. If an
authoritative string deliberately ends in whitespace, use an explicit YAML
escape such as `\x20`; repository whitespace hooks must not silently alter the
rendered clinical output.

### 4.3 Deferred rules

A source may contain `deferred_rules` after `rules`. A deferred rule preserves
verbatim source wording whose machine condition cannot yet be represented
safely:

```yaml
deferred_rules:
  - rule_id: endometrial_msi_high
    description: Workbook statement for an interpreted MSI-H result.
    source_locator: Endometrierapport 17apr; MSI-H text
    template: |-
      <verbatim source wording>
    required_fact_contract:
      - interpreted MSI state enum containing MSI-H
      - authoritative biomarker method and validation state
    activation_note: >-
      A numeric MSI value must not be translated into MSI-H without an
      approved interpretation contract.
```

Deferred rules are validated and included in the immutable content hash, but
the evaluator never runs them. They are a controlled migration inventory, not
silent fallback behavior.

To activate one:

1. Define the authoritative typed fact and its units or enum.
2. Populate it before report-rule evaluation.
3. Register and test the fact path.
4. Move the rule from `deferred_rules` to `rules`.
5. Replace the prose fact requirement with exact `when` predicates.
6. Add boundary and verbatim golden cases.
7. Obtain clinical approval and increment the rule-set version.

## 5. Rule Families And Order

Families run in this fixed order:

1. `finding_text`
2. `result_text`
3. `summary_text`

### 5.1 Finding text

`finding_text` rules run once for every prepared finding. Within each finding,
rules are sorted by priority. A matched rule with `stop: true` prevents a
generic fallback from also describing that finding.

Use this family for:

- gene-specific wording;
- tier-specific wording;
- exon-specific wording;
- CNV or fusion finding descriptions.

### 5.2 Result text

`result_text` rules run once for the complete report context. Use them for
cross-finding or result-level statements, including a validated negative
result.

### 5.3 Summary text

`summary_text` rules run last and once per context. Use them for report
conclusions and standard final statements.

Rendered text is grouped by `section` in evaluation order. The full trace
records matched and rejected rules, missing facts, finding indexes, and
rendered text.

## 6. Condition Operators

All conditions in `when` use AND semantics.

| Operator | Meaning |
|---|---|
| `eq` | Actual value equals configured value |
| `ne` | Actual value differs |
| `in` | Actual scalar occurs in configured collection |
| `not_in` | Actual scalar does not occur in configured collection |
| `contains` | Actual collection or text contains configured value |
| `overlaps` | Actual and configured collections share at least one value |
| `exists` | Fact path exists or does not exist |
| `gt` / `gte` | Numeric or ordered greater-than comparison |
| `lt` / `lte` | Numeric or ordered less-than comparison |

Missing facts do not satisfy ordinary operators. They are recorded in the
trace. `exists` is the only operator intended to test absence explicitly.

Arbitrary Python expressions, regular expressions, database operators, and
unregistered document paths are not supported.

## 7. Approved Fact Registry

The registry is implemented in
`api/application/reporting/clinical_rules/registry.py`. A YAML source fails
validation when it uses any other path.

### 7.1 Sample and configuration

| Fact | Source |
|---|---|
| `sample.name` | Sample anchor |
| `sample.assay` | Bound ASP identifier |
| `sample.subpanel_id` | Bound sample subpanel |
| `sample.profile` | Deployment environment |
| `sample.omics_layer` | DNA or RNA |
| `sample.paired` | Case/control state |
| `sample.genome_build` | Reference build |
| `asp.*` | Exact active ASP used for report preparation |
| `aspc.*` | Exact ASPC supplied to the report workflow |
| `aspc.reporting.analysis` | Report-enabled analysis domains |
| `aspc.reporting.report_sections` | Rendered analysis sections |
| `applied_gene_lists` | Selected typed ISGL documents |

### 7.2 Findings

| Fact | Meaning |
|---|---|
| `finding.kind` | `snv`, `cnv`, `fusion`, or `translocation` |
| `finding.gene` | Single selected gene when applicable |
| `finding.genes` | All genes represented by the finding |
| `finding.tier` | Current resolved classification |
| `finding.exon` / `finding.intron` | Selected-transcript location values |
| `finding.case_vaf` / `finding.control_vaf` | Decimal allele fractions stored by the finding pipeline |
| `finding.case_vaf_percent` / `finding.control_vaf_percent` | Report-ready percentages derived once during context preparation |
| `finding.consequence` | Selected-transcript consequence terms |
| `finding.hgvsc` / `finding.hgvsp` | Selected-transcript HGVS values |
| `finding.variant_type` | Normalized finding type |
| `finding.cnv_effect` | Gain/loss interpretation supplied by CNV preparation |
| `finding.fusion_gene_1/2` | Structural finding partners |

The selected transcript is finalized before rule preparation. Rules cannot
choose another transcript or inspect arbitrary alternate transcripts.

### 7.3 Applied gene lists

`applied_gene_lists` contains the exact selected ISGL documents supplied to
report preparation. Each entry adds a `selected_for` array:

```yaml
- isgl_id: H-MGP
  version: 3
  selected_for: [snv, cnv]
  genes: [ASXL1, DNMT3A, FLT3]
```

DNA preparation includes selected `snvlists` and `cnvlists`. RNA preparation
includes selected `fusionlists`. The list's own type, version, and genes remain
available. Rules must not infer that a list was selected merely because one of
its genes appears in a finding.

### 7.4 Biomarkers and aggregates

The full `biomarkers` list is available to templates. New biomarker
conditions require a dedicated typed fact before activation.

Available aggregates include:

- total finding count;
- SNV, CNV, fusion, translocation, and biomarker counts;
- Tier I, II, and III counts;
- `tier_summaries`, containing ordered Tier I-III SNVs grouped by gene with
  rounded case-VAF labels;
- `has_tiered_snvs`, which reflects the reportable tier composition rather
  than the raw number of queried SNVs;
- `has_reportable_findings`.

The `tier_summary` template filter applies generic list composition to
`tier_summaries`. Every clinical word and connector passed to that filter,
including finding nouns, tier labels, sentence prefixes, and VAF phrases,
comes from YAML. Python owns grouping mechanics only.

## 8. Templates

Templates run in a Jinja `SandboxedEnvironment` with strict undefined values.
Only these root objects are available:

```text
sample
asp
aspc
applied_gene_lists
finding
biomarkers
aggregates
```

Unknown template variables fail compilation or rendering. Application and
Jinja default globals are removed. The only available filters are `default`,
`join`, `length`, `lower`, `round`, and `upper`. Templates cannot import
modules, call repositories, access application globals, or mutate source
objects.

Keep decision logic in `when`. Templates should express approved wording, not
reimplement clinical selection through large Jinja condition blocks.

## 9. Publication

Validate and publish an active source explicitly:

```bash
python3 scripts/publish_clinical_rules.py \
  clinical_reporting_rules/master_dna.yaml \
  --published-by <username>
```

The command above assumes the clinically approved source has been promoted
from `master_dna.draft.yaml` to the versioned active filename
`master_dna.yaml`. A draft filename and `status: draft` are never publishable.

The command reads `MONGO_URI` and `COYOTE3_DB`, validates the configured
collection name, compiles canonical content, inserts the release, and prints
the ASPC reference values.

Publication is not performed during API startup. Startup auto-synchronization
would make an application restart a clinical configuration change and is
therefore prohibited.

!!! warning
    Draft files validate structurally but cannot publish. Changing `status` to
    `active` without approval evidence and golden case IDs fails contract
    validation. Clinical approval and exact-output evidence are executable
    release prerequisites, not review comments.

### 9.1 Bind the published release

Publication does not activate a release for any assay. Use the authenticated
admin API to bind the printed release ID:

```bash
curl --request PUT \
  --header "Authorization: Bearer <access-token>" \
  --header "Content-Type: application/json" \
  --data '{"release_id": "<published-release-object-id>"}' \
  "https://<host>/<script-name>/api/v1/resources/aspc/<aspc-id>/clinical-rule-release"
```

The caller requires `assay.config:edit`. The API:

1. resolves the active ASPC;
2. resolves the immutable release by ObjectId;
3. requires release status `active`;
4. validates analyte, assay, assay group, subpanel, and environment scope;
5. constructs the complete release reference;
6. runs the normal ASPC validation and version-history logic;
7. retires the old active ASPC and inserts the replacement atomically at the
   repository boundary.

The request accepts only `release_id`. Clients cannot submit a rule-set ID,
version, or hash because those values are derived from the verified release.
This prevents a client from constructing an internally inconsistent reference.

## 10. Preview, Save, And Provenance

Preview:

1. rebuilds the filtered report context;
2. verifies the ASPC release reference;
3. verifies release scope and required facts;
4. evaluates rules;
5. includes generated text and the full trace in the temporary preview
   context;
6. writes no report history.

Save repeats preparation and evaluation on the server. It does not trust
client-provided text or HTML.

The saved report metadata records:

```yaml
clinical_rule_release:
  release:
    release_id: ...
    rule_set_id: ...
    version: ...
    content_hash: ...
  matched_rule_ids:
    - dna_tier_1_finding
    - dna_report_conclusion
```

This is stored with the filter snapshot, ASPC snapshot, report artifacts,
author, timestamp, and finding snapshots.

When generated clinical text exists and no explicit report conclusion comment
exists, the rendered report uses the generated text. An explicit reviewed
comment remains authoritative for the report conclusion.

DNA and RNA use the same lifecycle. Their prepared findings differ:

| Analyte | Findings supplied to the engine |
|---|---|
| DNA | Filtered reportable SNVs, CNVs, DNA translocations, configured fusions, and biomarkers |
| RNA | Classified, non-blacklisted, reportable fusion findings |

## 11. Adding Or Changing Rules

### 11.1 Existing facts and operators

For a rule based entirely on registered facts:

1. Select the assay/subpanel source file.
2. Describe the clinical intent.
3. Add the most specific rule before generic fallbacks.
4. Assign a unique priority in its family.
5. Add positive, negative, boundary, and missing-value fixtures.
6. Validate generated wording with clinical reviewers.
7. Increment the rule-set version.
8. Publish.
9. Create and validate the next ASPC version with the release reference.

### 11.2 New clinical concept

When a requested rule needs a fact that is not registered:

1. Identify the authoritative source collection or pipeline result.
2. Define its Pydantic field, type, units, allowed values, and missing state.
3. Populate it during ingest or an audited interpretation workflow.
4. Add it to `PreparedReportContext`.
5. Add the path to the fact registry.
6. Add extractor and contract tests.
7. Add rule-engine boundary tests.
8. Only then author and clinically validate the YAML rule.

Do not translate an informal label into a guessed database path.

## 12. Endometrial Draft

`clinical_reporting_rules/endometrial_dna.draft.yaml` records only workbook
conditions that can currently map to typed facts:

- POLE selected-transcript exons 9 through 14;
- POLE selected-transcript exons outside 9 through 14;
- TP53;
- the MMR genes `MLH1`, `MSH2`, `MSH6`, and `PMS2`;
- recurrent supporting genes explicitly listed in the workbook.

It is intentionally non-publishable. The final release still requires
confirmation of the real ASP/subpanel identifiers, selected-transcript exon
behavior, complete golden cases, and clinical approval. The executable text is
transcribed verbatim, including the source's punctuation and spacing.

The following workbook concepts are blocked:

| Concept | Reason |
|---|---|
| MSI-H, MSI-L, or unclear thresholds | Stored unit and approved thresholds are not yet defined |
| Low tumor-cell fraction decision | Required purity source and threshold are not approved |
| Normal/abnormal/complex CNV profile | Only an image exists; no typed interpreted status exists |

Their exact source text and explicit fact requirements are retained under
`deferred_rules`. The application must add these as explicit clinical facts
before the corresponding rules can be activated.

The workbook, the current implementation, and the archived Coyote reporting
code are migration references. They provide approved or previously used
conditions and wording. They are not runtime dependencies, and their
human-readable labels are never converted into guessed field names.

## 13. Validation Requirements

Every release requires:

- schema validation;
- fact-registry validation;
- restricted-template validation;
- deterministic content-hash test;
- scope tests;
- positive rule match;
- negative non-match;
- priority and stop-behavior test;
- missing-required-fact failure;
- preview no-write verification;
- saved provenance verification;
- clinically approved golden text fixtures.

The repository examples are reference inputs. Production activation remains a
governed clinical configuration change.
