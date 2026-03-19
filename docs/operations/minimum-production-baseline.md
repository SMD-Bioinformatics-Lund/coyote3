# Minimum Production Baseline

This is the minimum baseline for a production-grade Coyote3 deployment.

## Network and access

- Put UI/API behind a reverse proxy with TLS
- Restrict internal routes (`/api/v1/internal/*`) by network policy
- Restrict Mongo and Redis to private network only

## Secrets

- No `CHANGE_ME_*` values in runtime env files
- Secrets stored in a secret manager or secured env distribution
- Rotate `SECRET_KEY`, `INTERNAL_API_TOKEN`, DB credentials on schedule

## Database

- Dedicated Mongo instance for prod
- Auth enabled with least-privilege app user
- Daily backup and restore rehearsal

## Observability

- Centralized logs for web/api containers
- Health check and alerting for API endpoint and container restarts
- Track ingestion failures and auth/permission errors

## Release safety

- Run preflight and compose render before deploy
- Run smoke tests after deploy
- Keep rollback path to previous image/version

## Data governance

- No patient identifiers in public fixtures/repos
- Access controls reviewed periodically
- Retention and backup policy defined with clinical stakeholders
