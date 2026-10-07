# Environment file reference

An environment file is a private text file containing deployment settings, one
`NAME=value` assignment per line. It tells Coyote3 where its databases and files
are, which browser URL to use, and which credentials authenticate its services.
It is not a database, Python program, or clinical assay definition.

The filename is chosen by the operator. `.coyote3_env`, `production.env` and
`/srv/coyote3/config/production.env` are examples, not special filenames. Docker Compose
uses the file explicitly selected by `--env-file`.

## Format and examples

```dotenv
# Local HTTP example. These three settings combine into the browser URL.
PUBLIC_BASE_URL='http://localhost:6802'
SCRIPT_NAME='/coyote3'
COYOTE3_PORT='6802'
COYOTE3_NGINX_PUBLIC_SCHEME='http'

# A directory on the host, not a MongoDB database or browser URL.
COYOTE3_DATA_HOST_ROOT='/data/coyote3'
```

This example opens at `http://localhost:6802/coyote3/`. It is only a fragment:
copy `deploy/env/example.env` for the complete deployment template, then review
its values. For a center-facing HTTPS URL, a TLS ingress and certificate must
already terminate HTTPS; setting the scheme variable does not enable encryption
on the application's HTTP listener.

| Notation | Meaning | Example |
| --- | --- | --- |
| `NAME=value` | Sets one named option. Names are case-sensitive. | `ENV_NAME=production` |
| Single quotes | Literal text, suitable for spaces and special characters. | `ORGANIZATION_NAME='Molecular Diagnostics'` |
| `# comment` | An explanation, not a setting. Put comments on separate lines. | `# Production storage` |
| `NAME=''` | Explicit empty value. This is not always equivalent to omission. | `SCRIPT_NAME=''` serves the root path. |
| Omitted line | Uses the applicable default, or fails if required. | Omitting `COYOTE3_DB` fails application Compose validation. |

Use one assignment per name. Do not put YAML colons, TOML sections, passwords from
another environment, or shell commands in the file. Guides sometimes load the file
with `. "$COYOTE_ENV_FILE"`; that executes shell syntax, so source only a trusted
operator-controlled file. Literal assignments as above work for both Compose and
these shell commands. Do not print the file or full resolved Compose configuration
into shared logs: both can contain secrets.

## Supported keys, requirements and defaults

The [environment-variable table](../deployment/configuration-reference.md#environment-variable-reference)
is the authoritative key-by-key reference. It lists requirement, accepted value,
default when omitted and purpose. Defaults refer to the selected Compose/runtime
consumer, not to whatever example was copied into a private file.

| Classification | What to do |
| --- | --- |
| Required by application Compose | Supply a nonempty value. There is no usable deployment default. |
| Optional with a default | Omit unless the center needs a different value. A copied example value overrides the default. |
| Conditional | Required only when that integration or separate MongoDB deployment is enabled. |
| Runtime-only | Used by a process running directly on the host, or explicitly passed through a private Compose override. Adding it to `--env-file` alone does not inject it into a container. |
| Wrapper/internal | Calculated by deployment code or wired between services. Do not use it as a center override unless the reference explicitly supports that. |

For example, the template's `COYOTE3_PORT=6801` is an explicit example. The base
production Compose fallback is `5815`; the installation guide explicitly selects `6802`. These are
three different values with different sources, not competing defaults.

## Which value wins?

### Choose the appropriate template

| Repository template | Purpose | How to use it |
| --- | --- | --- |
| `deploy/env/example.env` | Application services, endpoints, identity and secrets. | Copy to a private file and complete the required settings before installation. |
| `deploy/env/example.mongo-local.env` | Connection examples for host-run development against local MongoDB. | Connection overrides only, not a complete deployment file. Container clients need a host-reachable address rather than `127.0.0.1`. |
| `deploy/env/example.mongo-split.env` | Application connection examples for independent application and knowledgebase servers. | Merge reviewed endpoint/name values into the application file after provisioning those servers. |
| `deploy/env/example.mongo-server.env` | Provisioning settings for the separate MongoDB stack. | Keep separate from application configuration; follow [MongoDB deployment](../architecture/mongodb-topology.md). |
| `deploy/env/example.loadtest.env` | Synthetic load-generator settings. | Use only with the [load-testing procedure](../testing/load-and-capacity-testing.md), never as an application production file. |

Copying a template does not provision a database, grant access or make its example
credentials valid. The application and MongoDB-server files serve different processes.

### Value precedence

1. An exported variable in the operator shell takes precedence for Compose substitution.
2. The selected `--env-file` supplies values not overridden by that shell.
3. The Compose expression supplies its documented default or reports a required-value error.
4. Only values wired into a service's `environment` or build arguments reach that service.
5. Host-run application commands read their process environment; some runtime settings
   also load a repository `.env` without overriding already exported values.

The version-aware wrapper additionally derives the image tag and logging defaults.
Use the wrapper consistently. If you edit a file after exporting it, reload it or
open a clean shell; otherwise old exported values can continue overriding it.

The common Compose expression `${NAME:-value}` uses its fallback for an omitted
**or empty** value. `${NAME:?message}` requires a nonempty value. Other consumers
may distinguish omission and emptiness; check the variable's reference rather than
using an empty string to request a default.

## Select and validate a file

From the repository root:

```bash
COYOTE_ENV_FILE="/srv/coyote3/config/production.env"
bash scripts/deployment/validate_env_secrets.sh --env-file "$COYOTE_ENV_FILE"
bash scripts/deployment/compose-with-version.sh \
  --env-file "$COYOTE_ENV_FILE" -f deploy/compose/docker-compose.yml config --quiet
```

These checks do not start containers or write to databases. They detect missing
secrets and invalid Compose substitution; they do not prove credentials can connect
to MongoDB or that a clinical policy is approved. The installation/upgrade procedure
includes the additional configuration and service checks.

## Applying changes

| Change | Apply through |
| --- | --- |
| Runtime environment settings | Recreate affected containers; `restart` alone retains their previous environment. |
| Public prefix, frontend identity or other frontend build values | Rebuild the frontend and recreate affected services. |
| Container UID/GID build values | Rebuild the API image and verify persistent-path access before replacement. |
| Documentation identity | Rebuild the documentation image. |
| Database endpoints, project name, persistent roots or Redis credentials | An explicit infrastructure transition plan; these are not routine display changes. |

Use [upgrades and configuration changes](../deployment/application-upgrades.md)
for an installed center. Keep the file private, backed up and outside Git. It is
not replaced from the template during an application update.
