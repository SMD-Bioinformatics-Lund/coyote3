# Synthetic clinical workflow exercises

The `demo_data/clinical_workflows/` bundle provides
raw pipeline files and matching database examples for ingest, query policies,
filters, classification, comments and reporting. Use an isolated demonstration
deployment. It contains artificial evidence, including intentionally mismatched
coordinates and transcript annotations; external clinical knowledgebase matches
are not expected and must not be treated as validation results.

## 1. Prepare the demonstration deployment

Follow [Local disposable full-stack validation](disposable-stack-validation.md) or
[First installation](../deployment/first-installation.md). Use separate application,
identity, cache and storage settings from clinical work. The configuration loader
below accepts only a loopback MongoDB URI and application database names
`coyote3_demo` or `coyote3_demo_*`. MongoDB must be a writable replica-set member.
It neither connects to nor modifies the current center database automatically.

Install the normal baseline first: active assay groups, installed query sets,
roles and initial accounts. The bundle uses the release's group/query catalogs;
it does not install another copy of those definitions. Install HGNC/VEP references
if the deployed review UI requires them. The offline exporter uses no external
references, and uses deterministic fallback transcript selection.

Provide separate demonstration users for authoring, independent review and
publication, plus a read-only user. Give them the relevant roles and `testing`
environment/assay scopes. Use the
[default-role reference](../administration/installed-defaults.md#default-roles-and-initial-accounts)
for responsibilities. No credentials or accounts are included in the fixtures.

## 2. Install the demo configuration

Run from the repository root with development dependencies installed. Substitute
your local replica-set name and existing demo administrator:

```bash
.venv/bin/python scripts/bootstrap/install_demo_workflows.py \
  --mongo-uri 'mongodb://127.0.0.1:27017/?replicaSet=YOUR_REPLICA_SET' \
  --db coyote3_demo \
  --actor demo.admin
```

This prints a plan. Repeat with `--apply` to insert the validated configuration
and report-draft baseline revisions in one transaction. Existing fixture identities
cause the command to stop; nothing is overwritten. The loader does not ingest
samples, assign roles, publish rules or reset databases.

| Assay | Group / family | Configuration |
| --- | --- | --- |
| `demo_e2e_hematology` | hematology / panel-dna | Full synthetic DNA evidence |
| `demo_e2e_myeloid` | myeloid / panel-dna | Full DNA evidence; base and `demo_focus` ASPCs |
| `demo_e2e_solid` | solid / panel-dna | Solid-specific query comparison |
| `demo_e2e_tumwgs` | tumwgs / wgs | WGS group-query comparison |
| `demo_e2e_lymphoid` | lymphoid / panel-dna | Application-default query comparison |
| `demo_e2e_fusion` | fusion / panel-rna | RNA FUSION and QC only |
| `demo_e2e_wts` | wts / wts | RNA FUSION, EXPRESSION, CLASSIFICATION and QC |

All ASPCs are scoped to `testing`. DNA enables SNV, CNV, CNV_PROFILE, COVERAGE,
TRANSLOCATION, HRD, MSI, TMB and PGX. RNA has no SNVs. The focus ISGL contains
FLT3 and CEBPA; initially it is available for selection, not automatically applied.
The focus ASPC starts with the same filter values as base to isolate scope tests.

Report sets are **drafts**, language `en`. They include synthetic wording, tiered
SNV output and presence-based CNV/translocation/HRD/MSI/TMB sections. Review and
publish them through the reporting-rule workflow before normal report generation.
They contain no clinical assertions about the supplied measurements.

The drafts include 32 embedded cases: no-findings output, each SNV tier and
additional-evidence presence for DNA, plus the RNA summary cases. They pass
submission-time rule validation; independent review/publication is still required.

## 3. Validate and ingest the raw files

The bundle is at `demo_data/clinical_workflows/`. Copy the entire directory to a
private working directory before uploading: the submission tool acknowledges
successful manifests, so the tracked originals should remain unchanged.

All parsed evidence files are included. DNA manifests use one `biomarkers` JSON
for HRD, MSI and TMB; each measurement remains independently selectable in the ASPC.
The example contains TMB for testing, but a producer can omit it until supported.

The alignment fields `case_bam`, `case_bai`, `control_bam` and `control_bai` are
explicitly `null`. BAM/BAI files are not included or uploaded by these manifests.
Ingest and rule testing do not require them. To test IGV, provide a sorted case BAM
and matching BAI, plus control BAM/BAI for paired review, and configure their ASP
IGV folder and alignment-service access. Use the appropriate reference genome;
a design BED supplies an optional target track. See
[alignment resources](../reference/ingest-files/images-and-alignments.md).

```bash
DEMO_WORK="$(mktemp -d /tmp/coyote3-demo.XXXXXX)"
cp -R demo_data/clinical_workflows/. "$DEMO_WORK/"
for manifest in "$DEMO_WORK"/manifests/*.yaml; do
  .venv/bin/python scripts/ingest/validate_ingest_spec.py \
    --yaml "$manifest" --check-files
done
```

Obtain a scoped ingest token using the
[ingest authentication guide](../api/sample-ingestion.md) and expose it as
`COYOTE3_INGEST_TOKEN`. Set `COYOTE3_BASE_URL` to the demonstration application URL,
including its configured prefix and port. Then upload one sample first:

```bash
.venv/bin/python scripts/ingest/submit_ingest_manifest.py \
  "$DEMO_WORK/manifests/demo_myeloid.yaml" \
  --base-url "$COYOTE3_BASE_URL" --auth ingest
```

After its terminal success acknowledgement, ingest the remaining manifests in the
same way. Do not send files under `negative/` in the normal batch. All resource
paths resolve relative to each manifest. The manifest format and raw field
contracts are documented in [Sample manifest](../reference/sample-manifest.md)
and [Raw ingest formats](../reference/ingest-files/README.md).

## 4. Check ingestion and data availability

| Sample | Expected state |
| --- | --- |
| `DEMO_HEMATOLOGY`, `DEMO_MYELOID`, `DEMO_SOLID`, `DEMO_TUMWGS`, `DEMO_LYMPHOID` | Ready; 30 retained SNVs, 5 CNVs, 4 DNA structural findings, coverage, HRD/MSI/TMB and PGX data. One of the 31 raw VCF records is excluded by `FAIL_NVAF`. |
| `DEMO_MYELOID_FOCUS` | Same evidence, named subpanel `demo_focus`, matching focus ASPC. |
| `DEMO_MYELOID_UNPAIRED` | Same raw variant scenarios; only the case genotype is supplied. |
| `DEMO_MYELOID_MISSING` | Ready with HRD/MSI/TMB missing; no biomarker document. Missing optional files are shown as unavailable, not as zero measurements. |
| `DEMO_FUSION` | 2 RNA fusions and QC; no SNVs or RNA expression/classification. |
| `DEMO_WTS` | 2 RNA fusions plus expression, classification and QC. |

Inspect the data-status tooltip, sample metadata, selected transcript and annotation
vault. Compare shapes with `expected/after_ingest/`, allowing for real IDs, times,
paths and HGNC-dependent transcript provenance. The CNV profile PNG is a placeholder
for file handling and display, not a computed profile. The PGX object exercises the
current flexible data contract, not a validated diplotype interpretation pipeline.

## 5. Verify query rules and filters

Use `scenarios/variants.json` to locate each finding by its exact `simple_id`.
VCF IDs are human-readable labels; the application uses its derived finding identity.
The unchanged filters admit six ordinary records: `baseline_pass`, the three
`tier*_candidate` records, `depth_boundary` and `alt_reads_boundary`.

| Group | Additional selected labels | Total selected SNVs |
| --- | --- | --- |
| hematology, myeloid, tumwgs | `flt3_svtype`, `flt3_long_alt`, `marker_admitted`, `cebpa_germline`, `interval_first`, `interval_last` | 12 |
| solid | `tert_regulatory`, `nfkbie_binding`, `cebpa_germline`, `non_cebpa_germline` | 10 |
| lymphoid | None | 6 |

`low_af`, `low_depth`, `low_alt_reads`, `population_high`, `control_high`, incorrect
genes, short ALT, low-evidence FLT3 and positions just outside the admitted interval
provide negative controls. Germline admissions can bypass ordinary evidence in the
current somatic view; see the [SNV workflow warning](../administration/query-rules.md).

!!! important "VCF float boundary behavior"
    The parser reads VCF floating-point values with limited precision. The nominal
    `0.03` case fraction is slightly below the minimum after parsing; nominal `0.05`
    control fraction is slightly above the maximum. Therefore `af_boundary` and
    `control_boundary` are excluded by the current queries. These fixtures record
    actual behavior rather than treating decimal source strings as exact values.

The unpaired myeloid sample additionally selects `control_high` and
`control_boundary`, because there is no control genotype. Selecting only FLT3
returns three records: `tier2_candidate`, `flt3_svtype`, `flt3_long_alt`.
Select the focus ISGL to exercise FLT3/CEBPA gene restriction; clear it to restore
the original selection. Change sample filters and confirm sample-filter references
resolve the current values instead of copying them into a rule.

CNV filters initially select two of five records. The others exercise insufficient
ratio, undersized and oversized segments. Coverage exon values are 50, 100, 499,
500 and 800 for checking warning/error boundaries and display. Both RNA fusions
pass the zero-read defaults; setting minimum spanning reads to 10 and pairs to 5
retains only BCR–ABL1. Exercise caller/effect filters, translocation gene scope,
false-positive and irrelevant flags, and compare visible counts with exports.

The DNA structural VCF contains one annotated BCR–ABL1 breakend, a reciprocal
custom KMT2A–NPM1 feature pair, a TP53 deletion and a CEBPA duplication. Five input
records produce four stored findings. Check the pair's two `source_records`,
embedded SnpEff annotations, explicit DEL/DUP endpoints and interval identities
in exports. Custom partner ordering does not assert biological fusion direction.
These examples do not use real transcript accessions for MANE validation; the
isolated structural-parser tests supply synthetic HGNC reference records for that
selection hierarchy.

### Query authoring and inheritance

`scenarios/query_drafts.json` contains validated request examples. Use the `request`
object for authoring; `scenario` is a fixture label, not an API field. Test one
alternative at a time against the matching sample:

1. `assay_inherit`: inherited conditions remain unchanged and read-only in the
   composition preview; results match the group policy.
2. `assay_extend`: exclude TP53 at the myeloid assay scope. This also excludes
   TP53 findings otherwise admitted by germline exceptions. Other assays retain
   their results.
3. `subpanel_replace`: replace somatic exceptions with an empty list for
   `demo_focus`. This removes inherited FLT3 extensions; it does not remove the
   separately composed germline admissions. Base-scope samples remain unchanged.
4. `nested_logic`: exercise AND, OR and NOT using FLT3/CEBPA and marker predicates
   in the lymphoid assay. Inspect positive and negative condition traces.
5. Try draft deletion, independent approval, publication and retirement. Drafts
   must not affect live retrieval; a published child affects only its scope;
   retirement restores parent composition. Published versions cannot be deleted.

Use **Test with a sample** and the full effective preview before publication. Test
sample-filter references, manually entered gene lists, CNV, RNA fusion and
translocation conditions with the same evidence. Supported operators and field
types are specified in [Query condition fields](../reference/query-condition-fields.md).

## 6. Exercise tiering, annotations and comments

On `DEMO_MYELOID`, assign tiers 1, 2, 3 and 4 to `baseline_pass`,
`tier2_candidate`, `tier3_candidate` and `tier4_candidate` respectively. Use genomic
nomenclature for this exercise so the synthetic HGVS labels cannot accidentally
share a protein-level annotation. Add a sample comment and a finding comment,
hide a second comment, and verify author/time/hiding metadata and scope.

`expected/after_review/` illustrates those document contracts using the parsed
finding identities. Classification annotations are group/subpanel scoped and can
be shared by matching findings in other samples. Finding comments remain
sample-specific. The example annotations for the full and missing-result myeloid
samples are shared; they are not independent duplicate classifications.

Also exercise CNV, translocation and RNA-fusion classification/comment actions on
the supplied findings, annotation text, classification removal, false-positive and
irrelevant toggles, and restore them before the baseline report comparison. Confirm
that the read-only user cannot write and that an out-of-scope user cannot retrieve
the sample. These browser/API and authorization actions are manual deployment
checks; the offline exporter does not claim to execute them.

## 7. Test report rules, save and export

Preview the installed demo report drafts using **Test with a sample**. The DNA
intro renders once. Only tiers 1–3 receive the example per-finding sentence; the
tier-4 NFKBIE candidate receives none. Present CNV, translocation, HRD, MSI and TMB
evidence enables its corresponding synthetic section. The missing-result sample
has no HRD/MSI/TMB section. RNA drafts produce a synthetic fusion summary.

`expected/report_previews.json` contains real engine output for these constructed
review contexts. It does not prove report preparation selected the same findings;
verify that through the live preview. Coverage, PGX, RNA expression/classification
and QC are available for their analysis views but have no custom narrative logic
in this fixture's report sets.

Complete independent review and publication using separate users. Generate a
report, compare preview and saved content, export the PDF, and check report number,
rule-version provenance, reported-finding snapshots and audit events. Revise a
draft and confirm that an already saved report does not change. No fabricated
saved report, publication approval or audit trail is seeded to bypass this process.

## 8. Exercise rejected and repeated ingestion

Run the three `negative/` manifests individually after recording the sample count:

| Manifest | Expected rejection |
| --- | --- |
| `missing_required_file.yaml` | Required VCF path is unreadable. |
| `missing_aspc.yaml` | No ASPC exists for the `validation` environment. |
| `rna_with_snv.yaml` | RNA assay does not accept an SNV VCF resource. |

Confirm no ready sample or partial dependent data is left by a failed ingest.
Resubmit a successful manifest to check duplicate-name rejection. Use a working copy
and the supported update option to exercise intentional re-ingestion; verify
replacement counts and preservation of unsupplied measurements. Test transaction
rollback on a disposable MongoDB replica set, not against the in-memory exporter.

## Offline verification and portability

```bash
.venv/bin/python scripts/quality/export_demo_workflows.py --check
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_clinical_workflow_demo.py --no-cov
```

Automated checks cover real ingest parsing, collection contracts, group query
selection, evidence/gene restrictions, CNV/RNA thresholds, query-draft grammar,
example tiers/comments and report-engine rendering. They use an in-memory store;
they do not validate MongoDB transactions, UI behavior, authentication, transport,
Celery, PDF rendering, external references, or every possible administrator rule.
Record those results during the deployment exercises above.

The raw bundle has no deployment paths, credentials or patient data and can move
to a separate repository. The exporter and tests depend on the application's
current contracts. Maintain a fixture/application version pairing when distributing
them separately. Changes to expected outputs require review; regeneration alone
does not establish that a clinical behavior change is correct.
