# Operations Verification Report (2026-03-11)

## Scope
This report captures execution evidence for:
1. Portable/dev runtime smoke validation (UI/API route health).
2. Backup and restore drill for patient-data persistence assurance.
3. Security/operational checks relevant to authentication and data durability.

Environment:
1. Host: WSL2 + Docker.
2. Stack: `coyote3_dev_*` compose services.
3. Date: 2026-03-11.

## 1. Runtime Smoke Verification
Command:
```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/ui_crawl_playwright.py
```

Observed result:
1. `login_success=true`
2. `login_user=coyote3.admin@skane.se`
3. `broken=[]` (no failing GET/POST probes in crawl output)
4. High-coverage traversal included:
   - dashboard and samples
   - admin users/roles/permissions/panels/config/genelists/schemas
   - sample-specific DNA pages
   - public assay catalog routes

Interpretation:
1. UI-to-API route wiring is healthy for core authenticated workflows in this environment.
2. Local-login allowlisted account path is functioning.

## 2. Backup/Restore Drill (Non-Destructive)
### 2.1 Backup execution
Command:
```bash
./scripts/mongo_backup_archive.sh \
  --mongo-uri mongodb://coyote3_dev_mongo:27017 \
  --db coyote_dev_3 \
  --out-dir .internal/drills/mongo_backups \
  --label restore-drill \
  --docker-network coyote3-dev-net
```

Output artifacts:
1. Archive: `.internal/drills/mongo_backups/coyote_dev_3_20260311T140633Z_restore-drill.archive.gz`
2. Metadata: `.internal/drills/mongo_backups/coyote_dev_3_20260311T140633Z_restore-drill.archive.gz.meta`
3. SHA256: `0d02a22904266e62cd1081ca2d80fcfc92cb32049a9599ad1cb00122c1f605d5`

### 2.2 Isolated restore execution
Restore target:
1. Isolated temporary Mongo container: `coyote3_restore_drill_mongo`
2. Network: `coyote3-restore-net`

Command:
```bash
./scripts/mongo_restore_archive.sh \
  --mongo-uri mongodb://coyote3_restore_drill_mongo:27017 \
  --db coyote_dev_3 \
  --archive .internal/drills/mongo_backups/coyote_dev_3_20260311T140633Z_restore-drill.archive.gz \
  --drop \
  --confirm RESTORE_PATIENT_DATA \
  --docker-network coyote3-restore-net
```

Restore summary:
1. `293994 document(s) restored successfully`
2. `0 document(s) failed`

### 2.3 Count parity verification
Key collection counts were compared between source and restored DB:

| Collection | Source (`coyote3_dev_mongo`) | Restored (`coyote3_restore_drill_mongo`) |
|---|---:|---:|
| users | 34 | 34 |
| roles | 8 | 8 |
| permissions | 64 | 64 |
| schemas | 7 | 7 |
| assay_specific_panels | 8 | 8 |
| asp_configs | 14 | 14 |
| insilico_genelists | 31 | 31 |
| samples | 10 | 10 |
| variants | 34350 | 34350 |
| cnvs | 101 | 101 |
| translocations | 0 | 0 |
| fusions | 0 | 0 |
| reported_variants | 2865 | 2865 |
| blacklist | 5375 | 5375 |

Result:
1. Count parity confirmed across checked workflow-critical collections.

## 3. Security and Reliability Notes
1. Login flow validated via local allowlisted admin identity in running stack.
2. Runtime boundary guardrails and route-contract tests are in place and passing locally.
3. Backup/restore scripts now support `--docker-network`, required for containerized topology reliability in WSL/docker-networked environments.

## 4. Residual Work (Non-execution items)
1. Push commits and run updated quality workflow in remote CI.
2. Perform scheduled periodic restore drills (weekly/monthly) and retain evidence.
3. Extend operational evidence package with latency/error-rate snapshots if required by governance.
