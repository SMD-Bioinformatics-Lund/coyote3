# Deployment and Operations

## Deployment options

- `docker-compose.yml`
- `docker-compose.dev.yml`
- `scripts/install.sh`
- `scripts/install.dev.sh`

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
