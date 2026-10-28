# Synthetic clinical workflow exercises

For the directory layout, sample manifest, analysis formats and offline mongomock
replay, see the [demo data bundle reference](demo-data-bundle.md).

The `demo_data/clinical_workflows/` bundle provides
raw pipeline files and matching database examples for ingest, query policies,
filters, classification, comments and reporting. Use an isolated demonstration
deployment. It contains artificial evidence, including intentionally mismatched
coordinates and transcript annotations; external clinical knowledgebase matches
are not expected and must not be treated as validation results.

## 1. Prepare the demonstration deployment

Follow [Local disposable full-stack validation](disposable-stack-validation.md) or
[First installation](../deployment/first-installation.md). Use separate application,
identity, cache and storage settings from clinical work. MongoDB must be a writable
replica-set member. The administrative installer uses the deployment's configured
application database and requires an authenticated, authorized operator.

Install the normal baseline first: active assay groups, installed query sets,
roles and initial accounts. The bundle uses the release's group/query catalogs;
it does not install another copy of those definitions. Install HGNC/VEP references
if the deployed review UI requires them. The offline exporter loads packaged HGNC
references without contacting external services.

Provide separate demonstration users for authoring, independent review and
publication, plus a read-only user. Give them the relevant roles and `testing`
environment/assay scopes. Use the
[default-role reference](../administration/installed-defaults.md#default-roles-and-initial-accounts)
for responsibilities. No credentials or accounts are included in the fixtures.

## 2. Install the demo configuration

### Administration interface

Open **Administration → Demo installation** with the `demo:install` permission.
The bundled `demo_installer`, `admin` and `sys_admin` roles include this permission.
The emergency `superuser` can also install demonstrations. Existing
installations must synchronize their [RBAC catalog](../administration/system-role-catalog.md)
before assigning it. Read the installation summary and acknowledge that the data
is synthetic, then choose:

- **Install starter demo and samples** for the connected hematology DNA and RNA
  fusion workflows. Configuration commits first; `DEMO_STARTER_DNA` and
  `DEMO_STARTER_RNA` are then processed by normal ingest.
  A retry after an ingest failure reuses the committed configuration and retries the
  sample. Existing sample content is never replaced.

## Demo resource relationships

One `setup/` bundle supplies both default installation and additional scenarios.
Biological groups are `hematology` and `solid`. The registry also retains `myeloid`
and `lymphoid` for legacy samples and `pgx` for pharmacogenomics. None of the new
demo assays use a technology or analysis type as their group.

| Group | Shared diagnosis | DNA panel | DNA WGS | RNA assays |
| --- | --- | --- | --- | --- |
| Hematology | MPN | `demo-hematology_gmsv1`, `demo-myeloid_gmsv1` | `demo-tumwgs-hema` | - |
| Hematology | CLL | `demo-hematology_gmsv1`, `demo-lymphoid_gmsv5` | `demo-tumwgs-hema` | `demo-gms_rnafusionv5`, `demo-wts-hema` |
| Solid | Lung | `demo-solid_gmsv3` | `demo-tumwgs-solid` | `demo-wts-solid` |
| Solid | Breast | `demo-solid_gmsv3` | `demo-tumwgs-solid` | - |
| Hematology | Myeloid | `demo-hematology-training` | - | - |
| Hematology | Lymphoid | - | - | `demo-rna-training` |

All associations are explicit records. The combined hematology panel covers a
synthetic set of genes; its name does not imply MPN or CLL eligibility. Each
diagnosis association has its own configuration. MPN is directly selectable;
selecting myeloid first is not required.

### Same diagnosis, different sequencing assay

`DEMO_MPN_PANEL` uses `demo-hematology_gmsv1::mpn::testing`;
`DEMO_MPN_WGS` uses `demo-tumwgs-hema::mpn::testing`. Both select `mpn-variants`
for SNV and CNV analysis. The synthetic panel SNV depth threshold is 100 and
the WGS threshold is 30. These demonstrate independent configuration, not
clinically validated thresholds or performance claims.

CLL and lung provide the same paired scenarios. `cll-variants`, `lung-variants`
and `breast-variants` support both SNV and CNV. `cll-fusion` is shared by the RNA
panel and WTS assay. Lists retain their own identities and revisions; they are
not copies of assay documents. Effective scope depends on selected lists and
the selected assay's validated gene coverage.

Samples pin exact configuration revisions with native ObjectIds. Configurations
capture assay resources and gene lists. Query policies and report rules resolve
independently from current published scopes. MPN panel and
WGS reporting rules have distinct assay scopes. Classification reuse and report
eligibility follow the annotation context, not a shared gene-list name.

### Default samples and catalog

The default samples are `DEMO_STARTER_DNA` on `demo-hematology-training` / `myeloid`
and `DEMO_STARTER_RNA` on `demo-rna-training` / `lymphoid`. Both belong to hematology.
The installation includes 11 assays, six shared diagnoses, 15 explicit diagnosis
links, eight reusable lists and 39 configurations. Testing configurations serve
the samples; 15 production configurations support synthetic catalog offerings.

The catalog presents biological group → diagnosis → modality and sequencing
family → assay. Its 15 offerings capture the linked resources and effective gene
scopes. MPN can therefore be compared across panel and WGS offerings. Turnaround
values are illustrative and no service prices are advertised.

The catalog is published only if the center has no public catalog. Otherwise,
the demo publication remains a draft. Demo report rules are packaged synthetic
examples, not center approval for clinical use. No saved report is created.

### Install additional scenarios

Under **Additional workflow scenarios**, select **Install configuration only**
or **Install configuration and samples**. Both use the same resource bundle as
the default installation. The page skips configuration already present and
ingests missing samples independently. A failed sample does not remove completed
samples. Conflicting resource identities require administrator review.

Installation requires `demo:install`; clinical viewing requires separate assay,
environment and review permissions. No identity records, external knowledgebase
releases or BAM files are included. The normal application baseline and a working
ingest service must already be available.

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
same way. Do not send files under `tests/fixtures/clinical_workflows/negative/` in the normal batch. All resource
paths resolve relative to each manifest. The manifest format and raw field
contracts are documented in [Sample manifest](../reference/sample-manifest.md)
and [Raw ingest formats](../reference/ingest-files/README.md).

## 4. Check ingestion and data availability

| Sample | Expected state |
| --- | --- |
| `DEMO_HEMATOLOGY`, `DEMO_MYELOID`, `DEMO_SOLID`, `DEMO_TUMWGS`, `DEMO_LYMPHOID` | Ready; 30 retained SNVs, 5 CNVs, 4 DNA structural findings, coverage, HRD/MSI/TMB and PGX data. One of the 31 raw VCF records is excluded by `FAIL_NVAF`. |
| `DEMO_MYELOID_FOCUS` | Same evidence, named diagnosis `mpn`, matching focus ASPC. |
| `DEMO_MYELOID_UNPAIRED` | Same raw variant scenarios; only the case genotype is supplied. |
| `DEMO_MYELOID_MISSING` | Ready with HRD/MSI/TMB missing; no biomarker document. Missing optional files are shown as unavailable, not as zero measurements. |
| `DEMO_FUSION` | 2 RNA fusions and QC; no SNVs or RNA expression/classification. |
| `DEMO_WTS` | 2 RNA fusions plus expression, classification and QC. |
| `DEMO_GROUP_DNA` | `solid` group WGS sample with small variants, CNVs, structural events, coverage, biomarkers and PGX. |
| `DEMO_GROUP_RNA` | `solid` group WTS sample with fusions, expression, classification and QC. |

Inspect the data-status tooltip, sample metadata, selected transcript and annotation
vault. Compare shapes with `tests/fixtures/clinical_workflows/expected/after_ingest/`, allowing for real IDs, times,
paths and HGNC-dependent transcript provenance. The CNV profile PNG is a placeholder
for file handling and display, not a computed profile. The PGX object exercises the
current flexible data contract, not a validated diplotype interpretation pipeline.

## 5. Verify query rules and filters

Use `tests/fixtures/clinical_workflows/scenarios/variants.json` to locate each finding by its exact `simple_id`.
VCF IDs are human-readable labels; the application uses its derived finding identity.
With no selected diagnosis list, the base filters admit six ordinary records: `baseline_pass`, the three
`tier*_candidate` records, `depth_boundary` and `alt_reads_boundary`.

| Group | Additional selected labels | Total selected SNVs |
| --- | --- | --- |
| hematology and retained myeloid group | `flt3_svtype`, `flt3_long_alt`, `marker_admitted`, `cebpa_germline`, `interval_first`, `interval_last` | 12 |
| solid | `tert_regulatory`, `nfkbie_binding`, `cebpa_germline`, `non_cebpa_germline` | 10 |
| retained lymphoid group | None | 6 |

`low_af`, `low_depth`, `low_alt_reads`, `population_high`, `control_high`, incorrect
genes, short ALT, low-evidence FLT3 and positions just outside the admitted interval
provide negative controls. Germline admissions can bypass ordinary evidence in the
current somatic view; see the [SNV workflow warning](../administration/query-rules.md).

> **Important: VCF float boundary behavior**
>
> The parser reads VCF floating-point values with limited precision. The nominal
> `0.03` case fraction is slightly below the minimum after parsing; nominal `0.05`
> control fraction is slightly above the maximum. Therefore `af_boundary` and
> `control_boundary` are excluded by the current queries. These fixtures record
> actual behavior rather than treating decimal source strings as exact values.

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

`tests/fixtures/clinical_workflows/scenarios/query_drafts.json` contains validated request examples. Use the `request`
object for authoring; `scenario` is a fixture label, not an API field. Test one
alternative at a time against the matching sample:

1. `assay_inherit`: inherited conditions remain unchanged and read-only in the
   composition preview; results match the group policy.
2. `assay_extend`: exclude TP53 at the myeloid assay scope. This also excludes
   TP53 findings otherwise admitted by germline exceptions. Other assays retain
   their results.
3. `diagnosis_replace`: replace somatic exceptions with an empty list for
   `mpn`. This removes inherited FLT3 extensions; it does not remove the
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

`tests/fixtures/clinical_workflows/expected/after_review/` illustrates those document contracts using the parsed
finding identities. Classification annotations are group/diagnosis scoped and can
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

Preview the installed demo reports from the sample's **Reports** tab, or test the
rule sets using **Test with a sample**. The DNA
intro renders once. Only tiers 1–3 receive the example per-finding sentence; the
tier-4 NFKBIE candidate receives none. Present CNV, translocation, HRD, MSI and TMB
evidence enables its corresponding synthetic section. The missing-result sample
has no HRD/MSI/TMB section. RNA rules produce a synthetic fusion summary.

`tests/fixtures/clinical_workflows/expected/report_previews.json` contains real engine output for these constructed
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

Run the three `tests/fixtures/clinical_workflows/negative/` manifests individually after recording the sample count:

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
