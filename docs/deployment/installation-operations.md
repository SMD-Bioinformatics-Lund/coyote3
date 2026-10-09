# Installation operations

The center installer runs a selected set of deployment operations. Application
bootstrap, bundled reference installation and index maintenance are separate
commands; none requires the web application to be running.

Complete the MongoDB, environment-file and center-configuration prerequisites in
the [first installation guide](first-installation.md). Run commands from the
repository root. Use the same environment file and project name throughout:

```bash
COYOTE_ENV_FILE=/srv/coyote3/config/production.env
COYOTE_PROJECT=coyote3-prod
coyote_compose() {
  bash scripts/deployment/compose-with-version.sh \
    --env-file "$COYOTE_ENV_FILE" -p "$COYOTE_PROJECT" \
    -f deploy/compose/docker-compose.yml "$@"
}
```

The [environment reference](configuration-reference.md) describes endpoint,
database, network and directory settings. Secrets remain in the private environment
file. Do not put passwords or database URIs in command history.

## Stage selection

`--steps` accepts a comma-separated selection. Stages execute in the order below,
regardless of their order in the argument. The default selects all nine stages.
Secret validation and Compose rendering always run. Selecting bootstrap, indexes
or startup also validates center configuration and checks database state.

| Stage | Default | Operation and prerequisites | Standalone command |
| --- | --- | --- | --- |
| `network` | On | Create the configured application network only if absent. Docker must be running. | Installer with `--steps network` |
| `directories` | On | Prepare configured host directories and permissions. | `coyote_compose --prepare-directories config --quiet` |
| `build` | On | Build selected Compose images. Can take time; omit when the matching images already exist. | `coyote_compose build` |
| `validate` | On | Validate mounted center configuration and four MongoDB endpoints, then identify fresh/existing application state. Requires API image and network. | Validation commands below |
| `bootstrap` | On | Install application/identity baseline only on fresh targets; preserve existing installations. Requires initial account details. | Bootstrap command below |
| `indexes` | On | Inspect, create and verify application, identity and BAM indexes. Existing clinical collections may take time to index. No knowledgebase index inspection or creation in this stage. | Index commands below |
| `start` | On | Verify baseline and application indexes, then start services and wait for health. Does not build images. | `coyote_compose up -d --no-build --wait --wait-timeout 180` |
| `health` | On | Check API health and browser routes through the local HTTP proxy using its rendered published port (`COYOTE3_PORT`) and `SCRIPT_NAME`. Services must already be running. | Installer with `--steps health` |

To start an established installation without rebuilding or applying indexes:

```bash
bash scripts/deployment/install_center.sh \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  --compose-file deploy/compose/docker-compose.yml \
  --steps validate,start,health
```

Startup still checks required application indexes. If they are missing, run the
`indexes` stage explicitly. A stage selection does not disable safety gates.
Selecting `--skip-build` suppresses `build` even when included in `--steps`.

The local health check uses Compose's published proxy port, including overrides and
host-address bindings. The installer displays this verified address as **Local application**.
It separately displays **Public application** from `PUBLIC_BASE_URL`; this address
can point to a separate HTTPS ingress and is not checked by the installer. Verify external DNS,
TLS and ingress routing separately. For direct localhost access, its port should
match `COYOTE3_PORT` so application-generated links point to the correct listener.

To perform only application index maintenance:

```bash
bash scripts/deployment/install_center.sh \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  --compose-file deploy/compose/docker-compose.yml \
  --steps indexes
```

## Knowledgebase operations

Both operations below are **off by default** and independent of `--steps`.
They run after selected application bootstrap/index stages and before selected startup.
They also work when the application baseline already exists.

| Option | Operation | Requirements and limits |
| --- | --- | --- |
| `--with-knowledgebase-seeds` | Install bundled HGNC, VEP metadata and VEP diagrams | Knowledgebase write privileges; `--sys-admin-username` supplies provenance or is prompted. Populated collections are preserved. Does not download external releases or build indexes. |
| `--with-knowledgebase-indexes` | Plan, apply and verify knowledgebase indexes | Knowledgebase index privileges. Index creation can be expensive on large reference collections. No application, identity or BAM indexes are modified by this operation. |
| `--knowledgebase-maintenance-uri-file FILE` | Use separate credentials for the selected knowledgebase operations | Optional restricted file containing one URI to the same configured endpoint and database. Rejected when neither knowledgebase operation is selected. Runtime credentials remain unchanged. |

For a new empty knowledgebase, append both knowledgebase options to the normal
first-install command. If references are already installed and indexed, omit both.
Missing references can limit annotation and interpretation; installation success is
not a clinical readiness assessment. Review [required data](required-data.md).

Bundled references can also be installed independently:

```bash
coyote_compose run --rm --no-deps -T api \
  python3 scripts/bootstrap/install_reference_data.py --actor center.admin
```

`--actor` is the existing administrator username recorded in installation metadata.
`--reference-dir` optionally selects a mounted, reviewed reference pack; by default
the command uses the bundled release. Logical database names and URIs come from the
environment. Existing collections are not refreshed or replaced by this command.

Use the source-specific [knowledgebase import procedures](../reference/knowledgebases/README.md)
for external releases. Those standalone importers retain their own explicit write
options and may build the indexes needed to publish a release. The center installer's
flags do not change independently invoked importers.

## Standalone validation and bootstrap

```bash
coyote_compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks configuration
coyote_compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks state
```

The state command performs read-only endpoint checks and returns `fresh` or
`existing`; partial initialization stops with an error. It does not seed data.

For a fresh application and identity database, use the environment's database names:

```bash
coyote_compose run --rm --no-deps -it api sh -c '
  exec python3 scripts/bootstrap/bootstrap_database.py \
    --require-empty-target --db "$COYOTE3_DB" --identity-db "$IDENTITY_DB" \
    --sys-admin-username center.admin --sys-admin-email admin@example.org \
    --username emergency.admin --email emergency@example.org
'
```

Passwords are requested privately. This command installs accounts, RBAC and
application policies; it does not connect to the knowledgebase. `--with-demo-center`
adds synthetic center configuration on fresh targets. See
[bootstrap data flow](bootstrap-data-flow.md) for seed files and ownership.

## Standalone index maintenance

`manage_mongo_indexes.py` supports `status`, `plan`, `apply` and explicit `retire`.
Each accepts `--scope application|knowledgebase|all`; the default is `application`.
`application` includes the application, identity and BAM repositories and security
indexes. `knowledgebase` selects reference repositories only. Use `all` only when
maintenance of both groups is intended.

```bash
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py plan --scope application
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --scope application --summary
coyote_compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes-ready --scope application
```

Replace `application` with `knowledgebase` for separately scheduled reference index
maintenance. `--summary` prints counts and returns a nonzero status if any required
index remains missing or conflicting. Without it, the index command prints JSON.
`indexes` is a read-only precheck that permits missing indexes; `indexes-ready`
requires all selected indexes to be present. Neither check creates indexes.
No command automatically drops a conflicting index. Use the
[index maintenance runbook](../operations/maintenance-and-verification.md) for reviewed retirement.
