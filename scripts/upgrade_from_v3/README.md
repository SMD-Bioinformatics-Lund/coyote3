# Upgrade from Coyote v3

This package converts offline BSON exports of the v3 `coyote3` database.
It does not connect to the production source.

Follow the [v3 migration runbook](../../docs/migration_from_v3/migration-guide.md)
for the source inventory, mapping format, missing-data requirements, migration
order, target application, and recovery procedure.

## Commands in order

| Command | Purpose |
| --- | --- |
| `audit_source_schema.py` | Inventory every field and shape in all migrated source records before conversion |
| `prepare_source.py` | Index the documented v3 BSON snapshot with sample-reference checks |
| `inspect_record.py` | Write one original record and reconciliation digests to a private file |
| `migrate_configuration.py` | Validate explicit ASP, ASPC, ISGL, group, and subpanel mappings |
| `migrate_annotations.py` | Preserve shared annotation identities, scope, authors, and content |
| `migrate_blacklist.py` | Preserve blacklist entries and map assay-group scope |
| `backfill_sample_metadata.py` | Read reviewed TSV metadata or prepare later run/read patches |
| `migrate_sample.py` | Build one bundle of related findings, histories, snapshots, and VEP evidence |

Apply bundles with `scripts/migration_common/apply_bundle.py` against an isolated
local target. It defaults to read-only preflight and requires `--apply` for writes.
The source databases and production tunnel are rejected.

## V3 source details

Small variants use `variants`; CNVs use `cnvs`; DNA translocations use `transloc`.
`panel_cov` maps to `panel_coverage`. The source also contains `group_coverage`,
`biomarkers`, `annotation`, `reported_variants`, and interval `coverage`.

Samples can contain `profile`, `subpanel`, top-level file paths, flat filters,
and embedded comments/reports. Physical ASP and ASPC bindings are explicit review
inputs. Newer samples can include case/control run names and read counts; older
records may need the TSV backfill. Historical VEP versions are required for SNVs.

Users, roles, permissions, external knowledgebases, backup collections, and source
schema/index metadata are excluded.

## Specific target schema transitions

These maintenance tools apply only to their documented source shapes on a
separately approved restored target. They are not a production migration sequence.

| Script | Purpose |
| --- | --- |
| `migrate_assay_subpanels.py` | Register shared subpanels and assay associations |
| `migrate_reporting_policy.py` | Convert legacy report metadata into rule drafts |
| `migrate_reporting_rule_resolution.py` | Replace explicit rule bindings with scope resolution |
| `migrate_biomarker_analyses.py` | Convert aggregate selections to HRD, MSI, and TMB |
| `backfill_sample_ingest_provenance.py` | Recover attribution from durable creation receipts |
| `backfill_clinical_rule_revisions.py` | Capture missing historical revision baselines |
| `repair_clinical_rule_revision_hashes.py` | Repair the documented BSON hash discrepancy |

See [clinical rule migrations](../../docs/operations/migrations/clinical-rule-migrations.md)
for reporting maintenance prerequisites.
