# Repository Script Reference

The `scripts/` directory contains executable maintenance and validation tools for the
FastAPI, React, MongoDB, Celery, and center deployments. Run operator commands
from the repository root with the target environment explicitly configured.

The [script directory index](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/scripts/README.md) groups commands by purpose.
[V3 clinical migrations](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/scripts/upgrade_from_v3/README.md) have a dedicated
source contract and run order. [V2 clinical migrations](../migration_from_v2/README.md)
use `variants_idref` and `cnvs_wgs`. Both packages operate on offline BSON exports;
the [v2 procedure](../migration_from_v2/migration-guide.md) and
[v3 procedure](../migration_from_v3/migration-guide.md) specify their order.

> **Info:** A script can be operationally supported without being called automatically.
> Backup, restore, reference synchronization, and one-time seed imports are intentionally
> explicit operator actions.

## Execution classes

| Class | Execution responsibility |
| --- | --- |
| Automated | Invoked by CI, hooks, package commands, or another script. |
| Orchestrator | Runs several validation or deployment steps; inspect the individual results. |
| Manual operation | Requires an operator to select the target and follow the relevant runbook. |
| Internal helper | Used by another script rather than invoked as an operator command. |

## Clinical data upgrades

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `{migrate_from_v2,upgrade_from_v3}/audit_source_schema.py` | Manual operation | Before legacy conversion | Inventories every nested field, decoded BSON type, and object-key shape across the full offline export |
| `{migrate_from_v2,upgrade_from_v3}/prepare_source.py` | Manual operation | Legacy migration runbook | Indexes a version-specific BSON snapshot with sample-reference checks |
| `{migrate_from_v2,upgrade_from_v3}/inspect_record.py` | Manual operation | Reconciliation | Writes one original record and its digests to a private file |
| `migration_common/prepare_target.py` | Read-only operation | Before conversion | Validates preinstalled ASP, ASPC, ISGL, group, and subpanel records and exports a fingerprinted target catalog |
| `{migrate_from_v2,upgrade_from_v3}/migrate_annotations.py` | Manual migration | Shared clinical resources | Preserves annotation identities, scope, and clinical content |
| `{migrate_from_v2,upgrade_from_v3}/migrate_blacklist.py` | Manual migration | Shared clinical resources | Converts blacklist assay-group scope |
| `{migrate_from_v2,upgrade_from_v3}/migrate_sample.py` | Manual migration | Per-sample stage | Builds related findings, histories, saved snapshots, and VEP evidence |
| `{migrate_from_v2,upgrade_from_v3}/backfill_sample_metadata.py` | Manual operation | Metadata reconciliation | Reads reviewed TSV fields into supplements or later run/read patches |
| `migration_common/apply_bundle.py` | Manual migration | Isolated local target | Preflights and transactionally applies bundles with production endpoint guards |
| `upgrade_from_v3/migrate_d4_coverage_blacklist.py` | Manual migration | After assay-group configuration | Converts only exclusion-shaped v3 `group_coverage` records; measurements remain sample-scoped |
| `migration_common/{offline,commands,conversion,clinical_plan}.py` | Internal helper | Version-specific commands | Shares indexing, conversion, and reconciliation without source MongoDB access |
| `upgrade_from_v3/clinical_documents.py` | Internal helper | Clinical migration | Defines source-specific conversions with explicit metadata and current contract validation |

## First deployment and center validation

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `bootstrap/bootstrap_database.py` | Manual operation | First-deployment runbooks; composed CI verification | Initializes `IDENTITY_DB` with initial administrators and RBAC, `KNOWLEDGEBASE_DB` with HGNC/VEP references, and `COYOTE3_DB` with optional synthetic center data |
| `knowledgebase/migrate_reference_database.py` | Manual maintenance | Existing deployments | Backs up and moves HGNC/VEP to the knowledgebase database; removes the superseded subpanel collection only after checking current replacements |
| `deployment/center_preflight.sh` | Manual operation | Initial-deployment checklist | Validates secrets, Compose rendering, Mongo configuration consistency, ports, and optional seed or ingest inputs without writing data |
| `deployment/prepare_center_config.py` | Manual operation | Center configuration deployment | Validates and stages four center-owned files from a local directory or a pinned Git commit, records hashes, and refuses to overwrite an existing release |
| `bootstrap/build_seed_bundle.py` | Internal helper and manual operation | `bootstrap/bootstrap_database.py`; controlled seed preparation | Normalizes center seed sources into deterministic collection documents |
| `bootstrap/install_assay_groups.py` | Manual operation | Assay-group administration guide | Plans or installs missing group definitions without renaming existing scopes |
| `deployment/center_check.sh` | Manual operation | Composed CI verification | Runs authenticated health, baseline-resource, manifest-validation, and ingest checks after services are online |
| `bootstrap/validate_assay_consistency.py` | Automated | preflight, contract integrity, bootstrap, tests | Verifies ASP, ASPC, ISGL, sample, catalog, and reporting-rule references before import |
| `ingest/validate_ingest_spec.py` | Automated | `deployment/center_check.sh`; deployment checklist | Validates a DNA or RNA manifest through the current `SamplesDoc` contract and optionally checks every configured file path |
| `ingest/api_login.py` | Internal helper | bootstrap and composed-workflow scripts | Creates an authenticated API session for script-driven checks |
| `ingest/submit_ingest_manifest.py` | Manual operation | Sample ingestion guide | Submits a manifest through the authenticated ingest API |

The application does not provide an all-in-one first-run orchestrator. Database
provisioning, direct bootstrap, application startup, and sample ingest are
separate operational steps. The application stack always uses the configured
`COYOTE3_MONGO_URI`; the first local Coyote3 account is created before the API is
started through `bootstrap/bootstrap_database.py`.

## Quality and generated contracts

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `quality/run_quality_suite.sh` | Orchestrator | Developer and release workflow | Runs backend, frontend, contract, documentation, and browser quality stages |
| `quality/run_family_coverage_gates.sh` | Automated | CI; `quality/run_quality_suite.sh` | Enforces backend coverage thresholds by source family; `--from-existing` reuses the unified `.coverage` database so the complete backend suite runs once |
| `quality/check_contract_integrity.sh` | Automated | pre-commit; quality suite | Coordinates repository-local dependency, shell, generated-contract, permission-catalog, and documentation checks. It does not connect to an API or database. |
| `quality/check_shell_quality.sh` | Internal helper | `quality/check_contract_integrity.sh` | Runs syntax and ShellCheck validation for tracked shell scripts |
| `quality/check_dependency_consistency.py` | Internal helper | `quality/check_contract_integrity.sh` | Checks exported dependency requirements against `pyproject.toml` |
| `docs/check_markdown_links.py` | Internal helper | `quality/check_contract_integrity.sh`; tests | Rejects broken repository-local Markdown links |
| `quality/check_staged_sensitive_data.py` | Automated | pre-commit and CI | Blocks staged secrets, clinical identifiers, and unsafe fixture content |
| `docs/export_collection_contracts_doc.py` | Automated | contract integrity | Regenerates the collection-contract reference from Pydantic schemas |
| `docs/export_permissions_reference.py` | Automated | contract integrity | Regenerates the permission catalog from application-owned permission definitions |
| `release/sync-package-version.js` | Automated | frontend package lifecycle | Synchronizes the frontend package version with `api/version.py` |

## Deployment and database operations

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `deployment/compose-with-version.sh` | Operator entry point | Deployment documentation | Resolves the application version, validates environment secrets, and invokes Docker Compose consistently |
| `deployment/prepare_host_directories.py` | Automated helper | Compose wrapper during deployment or explicit preflight preparation | Creates missing application storage from resolved Compose mounts and verifies container access without changing existing ownership |
| `deployment/validate_env_secrets.sh` | Automated helper | compose wrapper and preflight | Rejects missing, empty, or placeholder runtime secrets; LDAP credentials remain login-time configuration |
| `database/mongo_backup_archive.sh` | Manual or infrastructure-scheduled operation | MongoDB recovery runbook | Creates complete oplog-consistent timestamped MongoDB archives, verifies them, and publishes only complete files |
| `database/mongo_restore_archive.sh` | Manual recovery operation | Backup and recovery runbook | Verifies and restores a complete MongoDB archive with explicit confirmation and oplog replay |
| `database/manage_mongo_indexes.py` | Manual operation | Maintenance and troubleshooting runbooks | Inspects repository/security index contracts, applies missing indexes, and retires one explicitly confirmed obsolete index |
| `database/inspect_mongo_capacity.py` | Manual operation | Maintenance and quality runbook | Emits a read-only collection count, storage/index-size, and index-inventory snapshot without reading clinical documents |
| `database/inspect_report_artifacts.py` | Manual operation | Report-artifact reconciliation guide | Compares report records with files and identifies missing, outside-root, and unreferenced artifacts without changing them |
| `maintenance/migrate_notification_retention.py` | Upgrade operation | Email and notifications guide | Removes destructive notification expiry indexes and marks existing administrative broadcasts; writes require `--apply` |

## Reference and RBAC maintenance

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `identity/sync_rbac_catalog.py` | Manual operation | RBAC maintenance documentation and tests | Adds missing application-owned permissions and roles while preserving center-owned policies |
| `identity/migrate_administrator_roles.py` | Upgrade operation | Permissions and access guide | Assigns an explicitly selected system administrator and installs bundled administrator responsibility boundaries |
| `knowledgebase/seed_clinpgx_genes_public.py` | Manual operation | ClinPGx integration guide | Imports an explicitly supplied official ClinPGx gene export into the configured public marker collection |
| `knowledgebase/migrate_knowledgebase_database.py` | Upgrade operation | MongoDB deployment and recovery guide | Copies external knowledgebase collections into `KNOWLEDGEBASE_DB`, verifies complete content, and optionally removes verified source collections |
| `identity/migrate_identity_database.py` | Upgrade operation | MongoDB deployment and recovery guide | Copies users, roles, permissions, API sessions, and audit events into `IDENTITY_DB`, verifies complete content and indexes, and optionally removes verified source collections |
| `knowledgebase/update_brca_exchange.py` | Manual operation | Knowledgebase snapshot update guide | Validates and atomically publishes a complete BRCA Exchange TSV release |
| `knowledgebase/update_civic.py` | Manual operation | Knowledgebase snapshot update guide | Validates and publishes matching CIViC feature and variant summary releases as one unit |
| `knowledgebase/update_tp53_database.py` | Manual operation | Knowledgebase snapshot update guide | Imports the NCI TP53 functional/structural variant release used by the TP53 detail card |
| `knowledgebase/update_cosmic.py` | Manual operation | Knowledgebase snapshot update guide | Streams and publishes one explicitly selected licensed COSMIC product archive |
| `knowledgebase/knowledgebase_update_common.py` | Internal helper | Knowledgebase updater scripts | Owns source provenance, staging, batch insertion, indexes, publication rollback, and release manifests |
| `knowledgebase/update_vep_metadata.py` | Manual operation | VEP metadata update guide | Builds and installs release-specific VEP reference metadata |
| `knowledgebase/update_vep_diagrams.py` | Manual operation | VEP metadata update guide | Downloads and installs release-specific VEP diagrams |
| `knowledgebase/repair_vep_reference_links.py` | Manual maintenance | VEP metadata update guide | Repairs reference links in seed metadata or an explicitly selected knowledgebase |
| `knowledgebase/migrate_vep_diagram_storage.py` | Upgrade operation | VEP metadata update guide | Moves embedded diagram payloads into the supported diagram storage format |
| `knowledgebase/vep_diagram_storage.py` | Internal helper | VEP import and migration commands | Separates diagram metadata from payloads and reads or writes diagram storage |
| `knowledgebase/ensembl_archives.json`, `knowledgebase/vep_metadata_policy.json` | Configuration inputs | VEP metadata update commands | Define archive locations and reference metadata policy |

## Operational prerequisites

Database maintenance commands require the target URI and database name, suitable
credentials, and any backup or writer-pause conditions stated in their runbook.
Inspect a read-only plan before applying a migration where the command supports it.
Do not assume that index creation, filesystem writes, or operations against different
MongoDB deployments share one transaction.

Use the [database recovery guide](../deployment/mongodb-setup-and-recovery.md) for backups and
restores, [reference database migration](../operations/migrations/knowledgebase-database-migration.md) for HGNC/VEP
relocation, and [knowledgebase updates](../operations/knowledgebase-updates.md) for controlled imports.
Keep credentials, exports, and backup files outside the repository.
