# Deployment and Operations

## Deployment options

- `scripts/compose-with-version.sh`
- `scripts/install.sh` (production wrapper)
- `docker-compose.yml`
- `scripts/install.dev.sh` (development wrapper)
- `docker-compose.dev.yml`

Use `scripts/compose-with-version.sh` as the default production compose entrypoint. It exports
`COYOTE3_VERSION` from `coyote/__version__.py` before invoking `docker compose`.

## Operational sequence

1. configure env vars/secrets
2. build image with version/build metadata
3. start redis sidecar
4. start coyote app container on expected network
5. verify app and smoke test critical routes

## Required operational checks

- Mongo connectivity and latency
- report storage mounts available
- logs writable
- RBAC-critical pages accessible for admin and blocked for regular users as expected

## Backup and recovery

- schedule Mongo backups
- test restore regularly
- verify report files are retained with metadata consistency

## Release checklist

1. tests/lint pass
2. changelog updated
3. image tagged and pushed
4. deploy config validated
5. smoke test done for login/samples/dna/rna/reports/admin
