# Release Readiness

This page is the entry point for deciding whether a Coyote3 build can be
promoted. It links to the authoritative procedures rather than duplicating
their commands.

## Required evidence

| Area | Required evidence | Procedure |
|---|---|---|
| Automated quality | Backend, frontend, contracts, typing, and strict documentation pass | [Test strategy and quality gates](../testing/testing_and_quality.md) |
| Clinical browser workflow | Public routes, login, one controlled DNA sample, one controlled RNA sample, report preview, and application controls pass through the deployed reverse proxy | [Browser and release validation](../testing/browser_and_release_validation.md) |
| Target-center acceptance | Authentication providers, representative DNA/RNA ingestion, reverse proxy, and isolated backup restoration pass with center-owned evidence | [Target-center acceptance](target_center_acceptance.md) |
| Deployment | Center preflight succeeds using the target environment and compose file | [Initial deployment checklist](initial_deployment_checklist.md) |
| Data protection | Backup completes and a restore has been rehearsed for the release environment | [Backup and recovery](backup_restore_and_snapshots.md) |
| Operations | Health, metrics, worker state, ingest timing, query timing, retention, and log rotation are observable | [Observability and alerts](observability_slos_and_alerts.md) |
| Compatibility | Supported manifest, collection, configuration, and reporting-rule contracts are unchanged or explicitly versioned | [Schema contracts and versioning](../developer/schema_contracts_and_versioning.md) |
| Limitations | Known clinical and operational limitations have been reviewed by the deployment owner | [Minimum production baseline](minimum_production_baseline.md) |

## Compose-backed browser gate

Run this gate after deploying the exact image and configuration intended for
promotion. The sample names must identify controlled validation records, never
clinical cases.

```bash
export COYOTE3_E2E_BASE_URL="https://validation.example.org/coyote3/"
export COYOTE3_E2E_USERNAME="release.validator"
export COYOTE3_E2E_PASSWORD="<from the secret store>"
export COYOTE3_E2E_DNA_SAMPLE="DNA_VALIDATION_001"
export COYOTE3_E2E_RNA_SAMPLE="RNA_VALIDATION_001"
cd frontend && npm run test:e2e:real
```

The real-service suite does not intercept API calls. A skipped authenticated
test therefore means the release gate is incomplete, not successful.

## Scheduled operational rehearsal

The `bootstrap-and-ingest-check` workflow runs manually, when a pull request is
labeled `full-stack-validation`, and every Monday at 03:17 UTC. It
starts an isolated disposable MongoDB replica set, initializes it through the
direct database bootstrap command, starts the stage application topology,
ingests the controlled DNA bundle, verifies the sample workflow, creates a
compressed MongoDB archive, restores that archive with replacement semantics,
and verifies the sample workflow again. This rehearsal complements the
per-change unit tests for log compression, retention deletion, and
failed-maintenance auditing.

The scheduled run is operational evidence, not a substitute for restoring a
backup from the target center before promotion. Record the center-specific
restore exercise in the approval record below.

## Approval record

Record the application version, image digest, configuration revision, clinical
rule revision, test output location, backup identifier, restore rehearsal date,
and approver in the center's controlled release system.

**Procedure verified:** 6 August 2026.
