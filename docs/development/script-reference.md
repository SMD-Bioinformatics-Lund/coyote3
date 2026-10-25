# Repository Script Reference

The `scripts/` directory contains executable maintenance and validation tools for the
FastAPI, React, MongoDB, Celery, and center deployments. Run operator commands
from the repository root with the target environment explicitly configured.

## Synthetic clinical workflow tools

`scripts/quality/run_transaction_tests.py` starts two temporary loopback MongoDB
replica sets, runs pytest with isolated database endpoints, and stops only its own
processes. It requires local `mongod` and the backend development environment:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- -q tests/integration
```

`scripts/release/verify_sdk_artifact.py` validates the retained wheel and release
record during Docker builds. It checks the checksum, package metadata, selected
versions and production source provenance. See
[release artifacts](../sdk/compatibility.md#build-and-record-an-application-release).

The [workflow guide](../testing/clinical-workflow-demo.md) documents the raw fixture
bundle and deployment exercises.

| Tool | Inputs and behavior |
| --- | --- |
| `scripts/bootstrap/install_demo_workflows.py` | Requires `--mongo-uri`, `--db`, `--actor`; plans validated configuration by default, inserts atomically with `--apply`. Restricted to loopback MongoDB and `coyote3_demo` database names. Requires the standard baseline, rejects existing fixture identities, and leaves report rules as drafts. |
| `scripts/quality/export_demo_workflows.py` | Replays the bundle offline through ingest and report evaluation using development dependencies. Writes deterministic expected artifacts; `--check` compares them without writes. Never reads deployment credentials or contacts a database. |

The [script directory index](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/scripts/README.md) groups commands by purpose.
[V3 clinical migrations](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/scripts/upgrade_from_v3/README.md) have a dedicated
source contract and run order. [V2 clinical migrations](../migration_from_v2/README.md)
use `variants_idref` and `cnvs_wgs`. Both packages operate on offline BSON exports;
the [v2 procedure](../migration_from_v2/migration-guide.md) and
[v3 procedure](../migration_from_v3/migration-guide.md) specify their order.

`scripts/migration_common/build_anno_vep.py` builds the shared historical transcript
reference and bounded MongoDB bundles from reviewed variant exports. Both version
packages provide `migrate_samples.py` to convert all selected samples and related
clinical collections. These are offline conversion tools; applying bundles is a
separate explicit operation against an isolated MongoDB target. SQLite files are
local lookup indexes, not the migration destination.

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
| `migration_common/prepare_target.py` | Read-only operation | Before conversion | Validates preinstalled ASP, ASPC, ISGL, group, and diagnosis records and exports a fingerprinted target catalog |
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
| `bootstrap/bootstrap_database.py` | First installation | First-deployment runbooks; composed CI verification | Creates initial accounts and installs application, knowledgebase and demo modules by default on fresh targets only; supports explicit module skip flags |
| `bootstrap/demo_service.py` | Internal helper | First installation | Binds the fixed starter bundle to normal transactional ingestion and configured databases |
| `deployment/manage_data.py` | Authenticated maintenance | [Installation operations](../deployment/installation-operations.md) | Uses API login and required password setup to add or force-repair explicitly selected modules; never deploys services |
| `deployment/install_center.sh` | Manual operation | First-installation guide | `--setup-center` installs the application baseline and bundled HGNC/VEP references; `--steps` selects individual stages; external imports and knowledgebase-wide indexing remain separate |
| `deployment/installation_checks.py` | Standalone command and helper | `install_center.sh` and guarded bootstrap | Read-only configuration, endpoint, installation-state and scoped index-readiness checks |
| `knowledgebase/migrate_reference_database.py` | Manual maintenance | Existing deployments | Backs up and moves HGNC/VEP to the knowledgebase database; removes the superseded diagnosis collection only after checking current replacements |
| `deployment/center_preflight.sh` | Manual operation | Initial-deployment checklist | Validates secrets, Compose rendering, Mongo configuration consistency, ports, and optional seed or ingest inputs without writing data |
| `deployment/prepare_center_config.py` | Manual operation | Center configuration deployment | Validates and stages three center-owned files from a local directory or a pinned Git commit, records hashes, and refuses to overwrite an existing release |
| `bootstrap/build_seed_bundle.py` | Internal helper and manual operation | `bootstrap/bootstrap_database.py`; controlled seed preparation | Normalizes center seed sources into deterministic collection documents |
| `bootstrap/install_assay_groups.py` | Manual operation | Assay-group administration guide | Plans or installs missing group definitions without renaming existing scopes |
| `bootstrap/install_query_rules.py` | Manual operation | Query-rule installation and upgrade guide | Validates bundled and TOML criteria, reports missing scopes, and inserts them transactionally with `--apply`; preserves every existing scope |
| `bootstrap/query_rule_seed.py` | Internal helper | Bootstrap and query-rule installer | Converts typed installation criteria into attributed version-one database policies; rejects unresolved group or unsupported assay/diagnosis scopes |
| `deployment/center_check.sh` | Manual operation | Composed CI verification | Runs authenticated health, baseline-resource, manifest-validation, and ingest checks after services are online |
| `bootstrap/validate_assay_consistency.py` | Automated | preflight, contract integrity, bootstrap, tests | Verifies ASP, ASPC, ISGL, sample, catalog, and reporting-rule references before import |
| `ingest/validate_ingest_spec.py` | Automated | `deployment/center_check.sh`; deployment checklist | Validates a DNA or RNA manifest through the current `SamplesDoc` contract and optionally checks every configured file path |
| `ingest/api_login.py` | Internal helper | bootstrap and composed-workflow scripts | Creates an authenticated API session for script-driven checks |
| `ingest/submit_ingest_manifest.py` | Manual operation | Sample ingestion guide | Submits a manifest through the authenticated ingest API |

`deployment/install_center.sh` orchestrates application installation against prepared
MongoDB endpoints. MongoDB provisioning and sample ingestion remain separate operations.
Existing installations skip bootstrap completely; partial or unrecognized targets
stop for inspection. The installer applies compatible indexes before application
startup and never drops or resets a database. Follow the
[first-installation guide](../deployment/first-installation.md#8-build-images-and-install-the-database-baseline)
for parameters, maintenance credentials and recovery boundaries.

The standalone [`gene_db_creation.py`](../operations/hgnc-gene-installation.md)
converts reviewed HGNC TSV and Ensembl BioMart CSV files into contract-valid gene
documents. `--apply --backup FILE` installs them into the configured knowledgebase;
the default creates a review artifact without database access.

## Quality and generated contracts

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `quality/run_quality_suite.sh` | Orchestrator | Developer and release workflow | Runs backend, frontend, contract, documentation, and browser quality stages |
| `quality/check_demo_workflow.py` | Operator / CI | Disposable full-stack validation | Reads ready synthetic starter samples through the public proxy using the typed HTTP client and revokes its session; credentials come from `ADMIN_USERNAME` / `ADMIN_PASSWORD`, and `--api-url` includes the proxy prefix. |
| `quality/run_family_coverage_gates.sh` | Automated | CI; `quality/run_quality_suite.sh` | Enforces backend coverage thresholds by source family; `--from-existing` reuses the unified `.coverage` database so the complete backend suite runs once |
| `quality/check_contract_integrity.sh` | Automated | pre-commit; quality suite | Coordinates repository-local dependency, shell, generated-contract, permission-catalog, and documentation checks. It does not connect to an API or database. |
| `quality/check_shell_quality.sh` | Internal helper | `quality/check_contract_integrity.sh` | Runs syntax and ShellCheck validation for tracked shell scripts |
| `quality/check_dependency_consistency.py` | Internal helper | `quality/check_contract_integrity.sh` | Checks exported dependency requirements against `pyproject.toml` |
| `docs/check_markdown_links.py` | Internal helper | `quality/check_contract_integrity.sh`; tests | Rejects broken repository-local Markdown links |
| `docs/lint_markdown.mjs` | Automated | `npm run docs:lint`; CI | Runs the root Markdown rules over source documentation; `npm run docs:test` checks the runner and math renderer |
| `quality/check_staged_sensitive_data.py` | Automated | pre-commit and CI | Blocks staged secrets, clinical identifiers, and unsafe fixture content |
| `docs/export_collection_contracts_doc.py` | Automated | contract integrity | Regenerates the collection-contract reference from Pydantic schemas |
| `docs/export_permissions_reference.py` | Automated | contract integrity | Regenerates permission and system-role catalogs from application-owned RBAC definitions |
| `release/sync-package-version.js` | Automated | frontend package lifecycle | Synchronizes the frontend package version with `release.toml` |
| `release/check_release.py` | Manual and quality gate | application/SDK release preparation | Validates independent release versions and records wheel identity, digest and source provenance. |
| `release/build_sdk.py` | Manual and CI | SDK release preparation | Builds a wheel from isolated distribution inputs, excluding stale local build outputs. |
| `docs/export_sdk_reference.py` | Manual | SDK interface documentation | Generates public signatures and docstrings in `docs/sdk/reference.md`. |

## Deployment and database operations

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `deployment/compose-with-version.sh` | Operator entry point | Deployment documentation | Resolves the application version, validates environment secrets, and invokes Docker Compose consistently |
| `deployment/python_runtime.sh` | Internal helper | Installer and Compose wrapper | Selects a supported host interpreter from `PYTHON_BIN`, the repository environment, or system Python; container commands use the image interpreter |
| `deployment/prepare_host_directories.py` | Automated helper | Compose wrapper during deployment or explicit preflight preparation | Creates missing application storage from resolved Compose mounts and verifies container access without changing existing ownership |
| `deployment/validate_env_secrets.sh` | Automated helper | compose wrapper and preflight | Rejects missing, empty, or placeholder runtime secrets; LDAP credentials remain login-time configuration |
| `database/mongo_backup_archive.sh` | Manual or infrastructure-scheduled operation | MongoDB recovery runbook | Creates complete oplog-consistent timestamped MongoDB archives, verifies them, and publishes only complete files |
| `database/mongo_restore_archive.sh` | Manual recovery operation | Backup and recovery runbook | Verifies and restores a complete MongoDB archive with explicit confirmation and oplog replay |
| `database/manage_mongo_indexes.py` | Manual operation | Maintenance and troubleshooting runbooks | Inspects repository/security index contracts, applies missing indexes, and retires one explicitly confirmed obsolete index |
| `database/inspect_mongo_capacity.py` | Manual operation | Maintenance and quality runbook | Emits a read-only collection count, storage/index-size, and index-inventory snapshot without reading clinical documents |
| `database/inspect_report_artifacts.py` | Manual operation | Report-artifact reconciliation guide | Compares report records with files and identifies missing, outside-root, and unreferenced artifacts without changing them |
| `database/verify_audit_chain.py` | Scheduled or manual verification | Audit and logging guide | Verifies traceability event hashes and compares independently retained checkpoints without modifying events |
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
