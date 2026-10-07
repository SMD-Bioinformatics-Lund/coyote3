# Compose files and storage overrides

A Compose file is a YAML description of application services: their images,
commands, environment values, mounted directories, networks and health checks.
Docker Compose reads it to create or replace containers. It does not describe an
assay, patient, sample or clinical reporting rule.

## Select the files for the task

| File | Use | Required or optional |
| --- | --- | --- |
| `deploy/compose/docker-compose.yml` | Production application services using independently configured MongoDB endpoints. | Required base for application deployment. |
| `docker-compose.dev.yml` | Development source mounts and development services. | Development overlay only; not a production file. |
| `docker-compose.stage.yml`, `docker-compose.test.yml` | Stage/test overrides. | Only for the corresponding environment. |
| Private `storage.yml` copied from `docker-compose.storage.example.yml` | Additional read-only pipeline input mounts. | Optional; configure its source and target first. |
| `docker-compose.mongo.yml` | Independently operated MongoDB deployment. | Not used when MongoDB is already provided. Its own environment/initialization rules apply. |
| `docker-compose.mongo-backup.yml` | Optional backup-directory mount for the separate MongoDB stack. | Use only with that stack and a configured backup directory. |
| `docker-compose.mail.yml` | Disposable local SMTP capture with Mailpit. | Optional testing tool; see [email configuration](../operations/email-and-notifications.md). |
| `docker-compose.loadtest.yml` | Separate synthetic load-test runner. | Optional testing tool; see [load testing](../testing/load-and-capacity-testing.md) for target restrictions and configuration. |

The application environment examples and MongoDB-server examples are different
files. Application URIs select where clients connect; server credentials and
replica-set/keyfile settings provision a database service. Changing a database
server's initialization variables does not rotate credentials in existing storage.

## YAML structure

| Key | Meaning | Behavior when omitted |
| --- | --- | --- |
| `services` | Named containers such as `api`, `worker`, `redis` and `proxy`. | No service is defined by an empty override; earlier files still provide the base. |
| `image` | Image tag to run. | Use the repository's supported service definitions rather than inventing image names. |
| `build` | Image build context, Dockerfile and build arguments. | Service must use an available image. Runtime environment changes do not replace build arguments. |
| `environment` | Variables explicitly passed into a container. | Host/`--env-file` values are not automatically forwarded. |
| `volumes` | Host directories or Docker volumes mounted at container paths. | An extra input directory is not visible inside the container without a mount. |
| `ports` | Published host port and container listener. | A service can remain internal to the Docker network. |
| `networks` | Service connectivity and external network names. | Follow the base stack wiring; its external network must already exist. |
| `depends_on` and `healthcheck` | Startup dependencies and readiness probes. | Running alone is not evidence of readiness; preserve the shipped checks. |

These are explanations of the keys used by Coyote3, not permission to remove
required service wiring. Keep ordinary center values in the environment and center
files. Add a private override only for an infrastructure requirement such as input mounts.

## Private input mount example

```yaml
services:
  api:
    volumes:
      - type: bind
        source: /srv/pipeline/results
        target: /inputs
        read_only: true
        bind:
          create_host_path: false
  worker:
    volumes:
      - type: bind
        source: /srv/pipeline/results
        target: /inputs
        read_only: true
        bind:
          create_host_path: false
```

The host source must exist and be readable by the configured container identity.
Manifests refer to the container path, such as `/inputs/run/example.vcf`.
The standard data-root mount does not also mount the same absolute host path inside
the container. Mount the input in every service that needs to read it; the shipped
storage example includes API, worker and beat.

Pass the base file first and the private override afterward:

```bash
bash scripts/deployment/compose-with-version.sh \
  --env-file /srv/coyote3/config/production.env \
  -f deploy/compose/docker-compose.yml \
  -f /srv/coyote3/config/storage.yml config --quiet
```

Use that same file list for validation, build, startup and future upgrades. Relative
paths in overrides are resolved relative to the first Compose file; absolute host
paths avoid ambiguity. Review the merged result privately because unredacted
`config` output includes credentials. `config --quiet` validates without printing it.

## Changes and ownership

Recreate affected services after changing mounts, environment or network wiring;
a container restart does not replace its configuration. Build again when image
build arguments change. Follow [upgrades and configuration changes](../deployment/application-upgrades.md)
for an installed center. Missing application data/log paths are prepared by the
wrapper; missing center files or pipeline inputs are not created as empty substitutes.
