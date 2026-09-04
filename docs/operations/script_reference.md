# Repository Script Reference

The `scripts/` directory contains executable maintenance and validation tools for the
FastAPI, React, MongoDB, Celery, and center-deployment architecture. It does not contain
the retired Flask runtime scripts. Every tracked script belongs to one of four supported
execution classes below.

> **Info:** A script can be operationally supported without being called automatically.
> Backup, restore, reference synchronization, and one-time seed imports are intentionally
> explicit operator actions.

## Execution classes

| Class | Meaning | Removal rule |
| --- | --- | --- |
| Automated | Called by CI, pre-commit, package scripts, or another tracked script | Remove only with its caller and replacement validation |
| Orchestrator | Coordinates several supported scripts into one workflow | Remove only after replacing the documented workflow |
| Manual operation | Run deliberately by an administrator for maintenance or reference data | Remove only when the capability is retired or moved into the application |
| Internal helper | Imported or invoked by another script; not a primary operator command | Remove together with its parent workflow |

## First deployment and center validation

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `bootstrap_database.py` | Manual operation | First-deployment runbooks; composed CI verification | Initializes `IDENTITY_DB` with the first local superuser and bundled RBAC, and initializes `COYOTE3_DB` with HGNC, VEP, and optional synthetic center data |
| `center_preflight.sh` | Manual operation | Initial-deployment checklist | Validates secrets, Compose rendering, Mongo configuration consistency, ports, and optional seed or ingest inputs without writing data |
| `build_seed_bundle.py` | Internal helper | Tests and controlled seed preparation | Normalizes center seed sources into deterministic collection documents |
| `center_check.sh` | Manual operation | Composed CI verification | Runs authenticated health, baseline-resource, manifest-validation, and ingest checks after services are online |
| `validate_assay_consistency.py` | Automated | preflight, contract integrity, bootstrap, tests | Verifies ASP, ASPC, ISGL, sample, catalog, and reporting-rule references before import |
| `validate_ingest_spec.py` | Automated | `center_check.sh`; deployment checklist | Validates a DNA or RNA manifest through the current `SamplesDoc` contract and optionally checks every configured file path |
| `api_login.py` | Internal helper | bootstrap and composed-workflow scripts | Creates an authenticated API session for script-driven checks |
| `seed_payload_utils.py` | Internal helper | bootstrap bundle scripts | Provides shared seed parsing and serialization behavior |

The application does not provide an all-in-one first-run orchestrator. Database
provisioning, direct bootstrap, application startup, and sample ingest are
separate operational steps. The application stack always uses the configured
`MONGO_URI`; the first local Coyote3 account is created before the API is
started through `bootstrap_database.py`.

## Quality and generated contracts

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `run_quality_suite.sh` | Orchestrator | Developer and release workflow | Runs backend, frontend, contract, documentation, and browser quality stages |
| `run_family_coverage_gates.sh` | Automated | CI; `run_quality_suite.sh` | Enforces backend coverage thresholds by source family; `--from-existing` reuses the unified `.coverage` database so the complete backend suite runs once |
| `check_contract_integrity.sh` | Automated | pre-commit; quality suite | Coordinates repository-local dependency, shell, generated-contract, permission-catalog, and documentation checks. It does not connect to an API or database. |
| `check_shell_quality.sh` | Internal helper | `check_contract_integrity.sh` | Runs syntax and ShellCheck validation for tracked shell scripts |
| `check_markdown_links.py` | Internal helper | `check_contract_integrity.sh`; tests | Rejects broken repository-local Markdown links |
| `check_staged_sensitive_data.py` | Automated | pre-commit and CI | Blocks staged secrets, clinical identifiers, and unsafe fixture content |
| `export_collection_contracts_doc.py` | Automated | contract integrity | Regenerates the collection-contract reference from Pydantic schemas |
| `verify_composed_workflow.py` | — | — | **Removed.** Sample readiness is now verified inline in the CI workflow via `curl` against the public proxy port. |
| `sync-package-version.js` | Automated | frontend package lifecycle | Synchronizes the frontend package version with `api/version.py` |

## Deployment and database operations

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `compose-with-version.sh` | Operator entry point | Deployment documentation | Resolves the application version, validates environment secrets, and invokes Docker Compose consistently |
| `validate_env_secrets.sh` | Automated helper | compose wrapper and preflight | Rejects missing, empty, or placeholder runtime secrets; LDAP credentials remain login-time configuration |
| `mongo_backup_archive.sh` | Manual or infrastructure-scheduled operation | MongoDB recovery runbook | Creates complete oplog-consistent timestamped MongoDB archives, verifies them, and publishes only complete files |
| `mongo_restore_archive.sh` | Manual recovery operation | Backup and recovery runbook | Verifies and restores a complete MongoDB archive with explicit confirmation and oplog replay |
| `manage_mongo_indexes.py` | Manual operation | Maintenance and troubleshooting runbooks | Inspects repository/security index contracts, applies missing indexes, and retires one explicitly confirmed obsolete index |
| `inspect_mongo_capacity.py` | Manual operation | Maintenance and quality runbook | Emits a read-only collection count, storage/index-size, and index-inventory snapshot without reading clinical documents |

## Reference and RBAC maintenance

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `sync_rbac_catalog.py` | Manual operation | RBAC maintenance documentation and tests | Adds missing application-owned permissions and roles while preserving center-owned policies |
| `seed_clinpgx_genes_public.py` | Manual operation | ClinPGx integration guide | Imports an explicitly supplied official ClinPGx gene export into the configured public marker collection |
| `migrate_knowledgebase_database.py` | Upgrade operation | MongoDB deployment and recovery guide | Copies external knowledgebase collections into `KNOWLEDGEBASE_DB`, verifies complete content, and optionally removes verified source collections |
| `migrate_identity_database.py` | Upgrade operation | MongoDB deployment and recovery guide | Copies users, roles, permissions, API sessions, and audit events into `IDENTITY_DB`, verifies complete content and indexes, and optionally removes verified source collections |
| `update_brca_exchange.py` | Manual operation | Knowledgebase snapshot update guide | Validates and atomically publishes a complete BRCA Exchange TSV release |
| `update_civic.py` | Manual operation | Knowledgebase snapshot update guide | Validates and publishes matching CIViC feature and variant summary releases as one unit |
| `update_tp53_database.py` | Manual operation | Knowledgebase snapshot update guide | Imports the NCI TP53 functional/structural variant release used by the TP53 detail card |
| `update_cosmic.py` | Manual operation | Knowledgebase snapshot update guide | Streams and publishes one explicitly selected licensed COSMIC product archive |
| `knowledgebase_update_common.py` | Internal helper | Knowledgebase updater scripts | Owns source provenance, staging, batch insertion, indexes, publication rollback, and release manifests |

## Deciding whether a script can be removed

1. Search CI, pre-commit, package scripts, Compose, documentation, and script-to-script calls.
2. Confirm that no supported manual capability depends on it.
3. Replace its callers with the equivalent direct command or inline step.
4. Remove or replace its tests and documentation in the same change.
5. Run `check_shell_quality.sh`, focused script tests, contract integrity, and strict MkDocs.
6. Record the retirement in the changelog when it changes deployment or operator behavior.

> **Warning**
>
> A script with no automatic caller is not necessarily unused. Database
> restore and reference import scripts are intentionally operator-invoked;
> their documented procedure is the supported entry point.
