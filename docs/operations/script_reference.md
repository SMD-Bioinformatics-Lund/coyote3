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
| `center_first_run.sh` | Orchestrator | Quickstart and deployment runbooks | Validates configuration, starts Compose, creates the first local superuser inside the API container, seeds empty baseline collections, and runs an ingest smoke check |
| `center_preflight.sh` | Automated helper | `center_first_run.sh`; initial-deployment checklist | Validates secrets, Compose rendering, Mongo configuration consistency, ports, seed dependencies, and optional ingest manifests |
| `bootstrap_center_collections.sh` | Orchestrator | CI bootstrap workflow; `center_first_run.sh` | Authenticates to the API and imports baseline collection bundles without overwriting populated collections |
| `bootstrap_local_admin.py` | Automated helper | CI bootstrap workflow; `center_first_run.sh` | Creates the first locked RBAC records and local superuser directly in an otherwise uninitialized database |
| `build_seed_bundle.py` | Automated helper | `bootstrap_center_collections.sh`; tests | Normalizes center seed sources into deterministic API import payloads |
| `center_check.sh` | Automated | CI bootstrap workflow; `center_first_run.sh` | Runs authenticated health, baseline-resource, manifest-validation, and ingest checks |
| `validate_assay_consistency.py` | Automated | preflight, contract integrity, bootstrap, tests | Verifies ASP, ASPC, ISGL, sample, catalog, and reporting-rule references before import |
| `validate_ingest_spec.py` | Automated | `center_check.sh`; deployment checklist | Validates a DNA or RNA manifest through the current `SamplesDoc` contract and optionally checks every configured file path |
| `api_login.py` | Internal helper | bootstrap and composed-workflow scripts | Creates an authenticated API session for script-driven checks |
| `seed_payload_utils.py` | Internal helper | bootstrap bundle scripts | Provides shared seed parsing and serialization behavior |

The former Compose `first-run` service was removed because it called a nonexistent
`compose_first_run.sh` and duplicated the host-side orchestrator. The supported first-run
entry point is `center_first_run.sh`. When Compose-managed MongoDB is enabled, its init
script creates the application database user; the first local Coyote3 account is then
created from inside the API container so internal Docker hostnames remain valid.

## Quality and generated contracts

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `run_quality_suite.sh` | Orchestrator | Developer and release workflow | Runs backend, frontend, contract, documentation, and browser quality stages |
| `run_family_coverage_gates.sh` | Automated | CI; `run_quality_suite.sh` | Enforces backend coverage thresholds by source family; `--from-existing` reuses the unified `.coverage` database so the complete backend suite runs once |
| `check_contract_integrity.sh` | Automated | pre-commit; quality suite | Coordinates generated-contract, assay, shell, and documentation integrity checks |
| `check_shell_quality.sh` | Internal helper | `check_contract_integrity.sh` | Runs syntax and ShellCheck validation for tracked shell scripts |
| `check_markdown_links.py` | Internal helper | `check_contract_integrity.sh`; tests | Rejects broken repository-local Markdown links |
| `check_staged_sensitive_data.py` | Automated | pre-commit and CI | Blocks staged secrets, clinical identifiers, and unsafe fixture content |
| `export_collection_contracts_doc.py` | Automated | contract integrity | Regenerates the collection-contract reference from Pydantic schemas |
| `verify_composed_workflow.py` | Automated | CI bootstrap workflow | Verifies the running composed API workflow with authenticated calls |
| `sync-package-version.js` | Automated | frontend package lifecycle | Synchronizes the frontend package version with `api/version.py` |
| `setup_git_hooks.sh` | Manual setup | Contributing guide | Installs the repository-managed pre-commit hook configuration |

## Deployment and database operations

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `compose-with-version.sh` | Operator entry point | Deployment documentation | Resolves the application version, validates environment secrets, and invokes Docker Compose consistently |
| `validate_env_secrets.sh` | Automated helper | compose wrapper and preflight | Rejects missing, empty, or placeholder runtime secrets; LDAP credentials remain login-time configuration |
| `mongo_backup_archive.sh` | Manual operation | Backup and recovery runbook | Creates timestamped MongoDB archives using the configured backup location |
| `mongo_restore_archive.sh` | Manual operation | Backup and recovery runbook | Restores a selected archive with explicit confirmation and target settings |
| `mongo_bootstrap_users.py` | Manual operation | Existing-volume recovery runbook | Creates or rotates the Mongo application user when an existing volume cannot use init scripts |
| `manage_mongo_indexes.py` | Manual operation | Maintenance and troubleshooting runbooks | Inspects repository/security index contracts, applies missing indexes, and retires one explicitly confirmed obsolete index |
| `inspect_mongo_capacity.py` | Manual operation | Maintenance and quality runbook | Emits a read-only collection count, storage/index-size, and index-inventory snapshot without reading clinical documents |

## Reference and RBAC maintenance

| Script | Class | Current caller or entry point | Purpose |
| --- | --- | --- | --- |
| `sync_rbac_catalog.py` | Manual operation | RBAC maintenance documentation and tests | Adds missing application-owned permissions and roles while preserving center-owned policies |
| `seed_clinpgx_genes_public.py` | Manual operation | ClinPGx integration guide | Imports an explicitly supplied official ClinPGx gene export into the configured public marker collection |

## Deciding whether a script can be removed

1. Search CI, pre-commit, package scripts, Compose, documentation, and script-to-script calls.
2. Confirm that no supported manual capability depends on it.
3. Remove or replace its tests and documentation in the same change.
4. Run `check_shell_quality.sh`, focused script tests, contract integrity, and strict MkDocs.
5. Record the retirement in the changelog when it changes deployment or operator behavior.

!!! warning
    A script with no automatic caller is not necessarily unused. Database
    restore and reference import scripts are intentionally operator-invoked;
    their documented procedure is the supported entry point.
