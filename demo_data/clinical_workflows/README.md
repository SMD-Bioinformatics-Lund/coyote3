# Synthetic clinical workflow dataset

This bundle contains artificial evidence for Coyote3 ingest, query, review and
reporting exercises. All names beginning with `DEMO_` and all evidence records are
synthetic. Gene symbols are real vocabulary, but coordinates, transcript identifiers,
HGVS strings and measurements are test values, not biologically validated findings.

The DNA structural VCF covers an annotated breakend, a reciprocal custom feature
pair, a deletion and a duplication. Its five source records produce four findings
with embedded SnpEff evidence and explicit interval endpoints.

Every manifest declares `case_bam`, `case_bai`, `control_bam`, and `control_bai`.
They are explicitly `null`: this bundle has no alignment files and does not test
IGV read review. Null does not fabricate a file or a control specimen. For IGV,
provide a coordinate-sorted case BAM and its matching BAI, and a control BAM/BAI
for paired review. Configure the ASP IGV folder and make those files available
through the alignment service. See [alignment resources](../../docs/reference/ingest-files/images-and-alignments.md).

The `biomarkers` manifest key points to one shared JSON containing synthetic HRD,
MSI and TMB values. Production files may omit TMB until the pipeline produces it.
The other raw evidence files are included; no additional file is needed for the
in-memory ingest replay. Live ingestion also requires the setup catalogs described
in the workflow guide. A design BED and the configured reference genome resources
are needed only for the corresponding browser tracks, not for parsing these findings.

Follow the [workflow guide](../../docs/testing/clinical-workflow-demo.md) for setup,
ingest, expected selections, review actions and reporting checks.

| Directory | Contents |
| --- | --- |
| `setup/` | Nine demo ASPs, ten testing ASPCs, a named subpanel/association, an ISGL and nine unpublished report-rule drafts. Includes dedicated DNA and RNA assays in the `demo` group. |
| `raw/` | Paired/unpaired VCFs, translocation VCF, CNVs, coverage, shared HRD/MSI/TMB JSON, PGX, RNA fusions/expression/classification/QC and a placeholder CNV profile image. |
| `manifests/` | Twelve valid pipeline manifests with relative resource paths. |
| `negative/` | Deliberately invalid missing-file, missing-ASPC and RNA/SNV manifests. |
| `scenarios/` | Stable raw-variant labels and editable query-rule draft requests. |
| `expected/after_ingest/` | Twenty collection snapshots produced by real ingest parsing, normalization and writes in an isolated in-memory database. Includes supporting configuration. |
| `expected/after_review/` | Contract-validated examples of tiers and sample/finding comments linked to the ingested examples; these are illustrative user actions, not ingest output. |
| `expected/report_previews.json` | Actual report-engine section output for six synthetic review contexts. These are previews, not saved report documents. |

The examples use Extended JSON for BSON IDs/dates. Export IDs are deterministic
substitutes and timestamps are fixed to `2026-01-01T00:00:00Z`; live ingest generates
its own IDs and times. References are substituted consistently. Absolute fixture
paths become bundle-relative paths. Do not import expected snapshots into a running
installation: ingest raw files and perform the review actions instead.

From the repository root, with development dependencies installed:

```bash
.venv/bin/python scripts/quality/export_demo_workflows.py --check
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_clinical_workflow_demo.py --no-cov
```

To refresh snapshots after an intentional contract change, run the exporter without
`--check` and review the diff. It never reads credentials or connects to MongoDB.
The in-memory gateway does not test transaction rollback, HTTP authorization, Celery,
browser behavior, PDF generation or external knowledgebase services. Those require
the application workflow described in the guide.

Raw files, setup records, scenarios and snapshots stay together so they can move to
a separate data repository. The exporter and regression checks currently depend on
Coyote3 Python modules and remain with the application. Pin the application revision
alongside a separately released fixture bundle; this is not a clinical truth dataset.
