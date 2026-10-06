# Independent measurement analysis configuration

Deployments using the generic `BIOMARKER` selection or `biomarkers` manifest key
require explicit conversion to HRD, MSI, and/or TMB. The migration does not
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
5. Update producer manifests and center vocabulary overrides to the independent
   file keys. Validate typed TMB objects; arbitrary legacy extra fields are
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
metadata, missing-file metadata, and measurement counts. Existing generic file
paths are retained under each selected key. The parser reads only that key's
measurement from a shared JSON file. A formerly required generic file becomes a
required file for **each selected analysis**; verify producer content before reuse.

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
