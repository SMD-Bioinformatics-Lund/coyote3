# Independent measurement analysis configuration

Deployments using the generic `BIOMARKER` analysis selection
require explicit conversion to HRD, MSI, and/or TMB. The `biomarkers` manifest key
remains the shared input file. The migration does not
infer which measurements a center intended to enable.

## Preparation

1. Back up the application database and stop ingest and configuration writers.
2. Review each affected ASP and ASPC, including revisions referenced by samples.
   Determine the individual analyses and required files for that assay.
3. Review clinical rules that declare or use `BIOMARKER`, iterate `biomarkers`,
   or reference `aggregates.biomarker_count`. Publish replacement
   releases with individual analysis blocks and appropriate measurement facts.
   The script reports active published generic releases and refuses to apply while
   any remain. Existing rule releases and their hashes are not rewritten.
4. Return affected unpublished assay setups to draft. Published setup and rule
   revision snapshots remain historical evidence; adapt a new draft before reuse.
5. Use one `biomarkers` manifest key and combined JSON input. Separate `hrd`, `msi`,
   and `tmb` file keys are not accepted. Validate typed TMB objects; arbitrary legacy extra fields are
   not converted into measurements. Preflight validates existing measurement
   documents and stops on incompatible shapes; correct those through an approved
   data-correction procedure before applying the migration.

## Plan and apply

Load the deployment's `COYOTE3_MONGO_URI` and `COYOTE3_DB` through its approved
environment mechanism. The following example explicitly replaces the generic
selection with HRD and MSI:

```bash
.venv/bin/python scripts/upgrade_from_v3/migrate_biomarker_analyses.py --analyses HRD MSI
```

The default is a read-only plan. Review the counts and configuration scope before
applying the same selection:

```bash
.venv/bin/python scripts/upgrade_from_v3/migrate_biomarker_analyses.py --analyses HRD MSI --apply
```

The selection applies to every generic selection in that database. If assays need
different replacements, update their managed configurations individually before
running a database-wide conversion; do not use one selection as a clinical default.

The transaction updates ASP/ASPC selections, affected draft setups, sample file
metadata, missing-file metadata, and measurement counts. Existing shared file
paths remain under `biomarkers`. Identical separate file references can be collapsed
to that key; conflicting references stop the migration before any writes. Produce
one combined JSON and reconcile its metadata before retrying. The script never
chooses between distinct source files or merges their contents. Required-file
policy requires the shared file, not every measurement; verify assay expectations
against the actual producer output.

Stored measurements, saved reports, reported findings, published setup snapshots,
and clinical rule revisions remain unchanged. The migration checks original
documents when writing and aborts if a concurrent writer has changed the plan.

## Verification

API consumers use the sample-scoped `/hrd`, `/msi`, and `/tmb` endpoints, with
matching response record keys. The generic `/biomarkers` endpoint is not available.
Rule collections are `hrd`, `msi`, and `tmb`; their source-document counts are
`aggregates.hrd_count`, `aggregates.msi_count`, and `aggregates.tmb_count`.

Validate configuration contracts, then ingest synthetic files covering each
selected analysis, a valid zero result, and a missing optional file. Confirm that
disabled analyses are absent from review and report previews, enabled analyses
have separate report rows, and previously saved reports remain accessible. Resume
writers only after these checks pass.
