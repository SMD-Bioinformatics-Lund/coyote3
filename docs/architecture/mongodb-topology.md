# MongoDB services and deployment topology

## Logical services

![Storage ownership by resource family](../assets/diagrams/database-resource-map.svg)

The map groups all configured collection families by logical service. Exact names
come from `adapters/mongo/src/coyote_mongo/config/collections.toml`; typed field definitions are in the
[MongoDB collection contracts](../reference/mongodb-collections.md). Reference
families such as COSMIC use multiple collections. Their presence does not imply
that every dataset is installed or enabled.

Database names select namespaces. Connection URIs select MongoDB deployments,
authentication, and replica-set discovery. Coyote4 never derives a host, port,
replica-set name, or filesystem path from a database name.

| Logical service | URI setting | Database setting | Ownership |
| --- | --- | --- | --- |
| `primary` | `COYOTE4_MONGO_URI` | `COYOTE4_DB` | Environment-specific samples, findings, reports, configuration, clinical rules, notifications, and ingest receipts. |
| `identity` | `IDENTITY_MONGO_URI` | `IDENTITY_DB` | Environment-specific users, roles, permissions, sessions, and audit events. |
| `knowledgebase` | `KNOWLEDGEBASE_MONGO_URI` | `KNOWLEDGEBASE_DB` | Shared platform reference datasets and release inventory. Default name: `coyote4_knowledgebases`. |
| `bam` | `BAM_MONGO_URI` | `BAM_DB` | Configured BAM-service records. |

Each service uses its explicit URI when supplied. An omitted auxiliary URI uses
`COYOTE4_MONGO_URI`; explicit service settings take precedence. All environments require
a configured URI. Local connection examples are provided in
`deploy/env/example.mongo-local.env`; runtime code does not select a default host
or replica set. Maintenance commands also require a configured or explicit URI.

`*_DB` selects the database independently of any URI path or `authSource`.
Services cannot select the same database on the same configured endpoint. Host order,
credential differences, and omitted versus explicit default port `27017` do not
make two MongoDB namespaces distinct. DNS aliases and SRV resolution still require
operator review because this configuration check does not perform DNS lookups.
The URI is passed to PyMongo unchanged: its path can still affect MongoDB's default
authentication database when `authSource` is absent. Set `authSource` explicitly
when credentials are stored outside the selected service database.

The collection map keeps the logical TOML sections `[primary]`, `[identity]`,
`[knowledgebase]`, and `[bam]`. Their names do not change when a database moves.
Different services may use the same database name on different deployments; they
must not share the same database on the same deployment.

## Environment isolation

Use separate primary **and identity** namespaces for environments that share a
MongoDB deployment. Sharing the identity database would share sessions and audit
events as well as users. Notifications remain in the environment's primary database.
Coyote4 does not automatically copy or synchronize identities in either direction.

| Environment | Primary example | Identity example | Knowledgebase example |
| --- | --- | --- | --- |
| Production | `coyote4` | `coyote4_identity_prod` | `coyote4_knowledgebases` |
| Development | `coyote4_dev` | `coyote4_identity_dev` | `coyote4_knowledgebases` |
| Staging | `coyote4_stage` | `coyote4_identity_stage` | `coyote4_knowledgebases` |
| Test | `coyote4_test` | `coyote4_identity_test` | `coyote4_knowledgebases` |

Standalone development defaults use `coyote4_identity`; this is suitable when that
namespace is dedicated to the local environment. The deployment templates use
explicit environment suffixes to avoid accidental sharing on a multi-environment
host. Existing database names are not automatically renamed or copied. Keep an
existing configured name until a deliberate migration is completed.

Any future identity synchronization must be explicitly one-way from canonical
production identity into non-production, excluding sessions, audit, notification,
and temporary credential state. The identity relocation command is a manual move
of one environment's data, not an environment synchronization mechanism.

## Single-instance development

One `mongod` can host every database in the table above. Configure one `dbPath`
for that process and initialize its single-member replica set once. Do not create
per-database `dbPath` directories or start another `mongod` for each logical name.

```dotenv
COYOTE4_MONGO_URI=mongodb://coyote4_app:URI_ENCODED_PASSWORD@127.0.0.1:27017/?authSource=admin&replicaSet=coyote4-rs
IDENTITY_MONGO_URI=mongodb://coyote4_app:URI_ENCODED_PASSWORD@127.0.0.1:27017/?authSource=admin&replicaSet=coyote4-rs
KNOWLEDGEBASE_MONGO_URI=mongodb://coyote4_app:URI_ENCODED_PASSWORD@127.0.0.1:27017/?authSource=admin&replicaSet=coyote4-rs
BAM_MONGO_URI=mongodb://coyote4_app:URI_ENCODED_PASSWORD@127.0.0.1:27017/?authSource=admin&replicaSet=coyote4-rs
COYOTE4_DB=coyote4_dev
IDENTITY_DB=coyote4_identity_dev
KNOWLEDGEBASE_DB=coyote4_knowledgebases
BAM_DB=coyote4_bam_dev
```

Provision the account with the restricted identity role and service grants, and
enable MongoDB authorization before using these settings. The same authentication
setup can be used in development, test, staging and production. Authentication is
not an installer prerequisite: credential-free connections produce a warning and
can proceed. Database-enforced audit protection requires the restricted runtime
role; application login and authorization are separate from database authentication.
See [MongoDB provisioning](../deployment/mongodb-first-setup.md).

These loopback URIs are for host-run processes. Docker clients of a host-installed
MongoDB need `host.docker.internal` or another reachable host, not their own
`127.0.0.1`. Replica-set advertised member addresses must also be reachable from
every client; changing only the seed address is insufficient.

## Optional Docker MongoDB

The base application Compose file starts no MongoDB service. Include
`deploy/compose/docker-compose.mongo.yml` only when using the provided containers:

| Profiles enabled | MongoDB services selected |
| --- | --- |
| None | No MongoDB containers or replica initializers. |
| `mongo` | `mongo` (network alias `mongo-app`) and `mongo_init`. |
| `mongo-kb` | `mongo-kb` and `mongo_kb_init`. |
| Both | Separate app and knowledgebase instances with independent replica sets and storage. |

The overlay joins the operator-created `COYOTE4_APP_NETWORK`. A shared
knowledgebase instance must belong to one platform deployment, not be started
again for each environment. Other stacks use its reachable URI through an
operator-managed network or DNS endpoint. Avoid duplicate service aliases on a
shared network.

Prepare persistent data directories and secret keyfiles before enabling a
profile. App MongoDB uses `COYOTE4_MONGO_DATA_HOST_ROOT` and
`COYOTE4_MONGO_KEYFILE_HOST_PATH`. Knowledgebase MongoDB uses
`KNOWLEDGEBASE_MONGO_DATA_HOST_ROOT` and `KNOWLEDGEBASE_MONGO_KEYFILE_HOST_PATH`.
Each process has one `/data/db`; split instances must never mount the same data
directory. Keyfiles must be readable by the MongoDB runtime UID and not publicly
readable. Bind addresses default to loopback; these examples do not configure TLS.

For one Docker MongoDB, set all service URIs to the authenticated `mongo-app`
endpoint. Set `MONGO_REPLICA_MEMBER_HOST=mongo-app:27017`. For split deployment,
review `deploy/env/example.mongo-split.env` for the application connection URIs.
Copy `deploy/env/example.mongo-server.env` to `.coyote4_dev_mongo_env` for server
credentials, keyfiles, storage, ownership, ports, and replica-set settings.
For split deployment set `KNOWLEDGEBASE_REPLICA_SET_NAME=coyote4-kb-rs` there.
Complete all required settings before initializing MongoDB. The server env needs
only its own settings plus database names for initial grants and the shared
network name; do not put application signing keys or SMTP credentials in it.

```bash
docker compose -p coyote4-dev-mongo --env-file .coyote4_dev_mongo_env \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo --profile mongo-kb up -d mongo mongo-kb
docker compose -p coyote4-dev-mongo --env-file .coyote4_dev_mongo_env \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo run --rm mongo_init
docker compose -p coyote4-dev-mongo --env-file .coyote4_dev_mongo_env \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo-kb run --rm mongo_kb_init
```

Omit the knowledgebase profile, service, and initializer for a single instance.
Use no Mongo overlay/profiles for externally managed MongoDB. First-time user
creation runs only against empty data directories. The provided init script
creates users in `admin`: use `authSource=admin` for those users. Existing users
and replica-set configurations are not silently rewritten.

## Knowledgebase access

The provided MongoDB app user has read/write access to app, identity, and BAM
data, but **read** access to knowledgebases. The split knowledgebase reader also
has only `read`. Use a separately provisioned maintenance account with appropriate
write/index/collection-administration privileges for imports and index setup.

Manual update commands select `KNOWLEDGEBASE_MONGO_URI` and `KNOWLEDGEBASE_DB`, or
explicit `--mongo-uri`/`--database` arguments. Controlled API refresh/write actions
still require application permissions **and** MongoDB write privileges. A read-only
deployment must run those operations through maintenance tooling or a deliberately
write-enabled administrative runtime; ordinary detail-page reads need no write role.
Do not give the public-serving runtime root credentials to make imports succeed.

## Connections and transaction boundaries

`adapters/mongo/src/coyote_mongo/config/endpoints.py` resolves endpoints. `MongoConnections` owns one client per
identical URI within a runtime/worker process, sharing the configured pool/timeouts.
Different credentials, URI options, or replica-set names use different clients.
There is no per-request client creation and no global client shared across worker
processes. Pools are closed on failed initialization and runtime store reset.

Sample/evidence/report/rule/catalog transactions stay on the primary service.
Knowledgebase transactions use their target collections' client. Identity writes
and audit delivery use identity repositories independently. No transaction or
snapshot guarantee spans separate MongoDB deployments.

Async generic collection ingestion requires its target and primary job receipt to
share the same client. Split-client targets receive HTTP 400 before job acceptance;
use synchronous ingestion or maintenance import instead. Workers also enforce this
boundary for queued work. Drain old tasks before relocating a target. Do not
replace this guard with non-transactional completion receipts.

## Endpoint configuration

1. Set `COYOTE4_MONGO_URI`; preserve the existing authentication path/options.
2. Set identity, knowledgebase, and BAM URIs independently where needed.
3. Set each service's database name explicitly. Database names are not inferred
   from the URI or normalized to another spelling.
4. Use logical section keys in TOML collection files and Python integrations
   consuming `DB_COLLECTIONS_CONFIG`. `get_mongo_settings` returns settings per
   logical service.
5. Apply indexes with maintenance credentials on all configured endpoints before
   starting API/workers. Runtime startup inspects contracts; it does not create indexes.
6. Restart API, workers, and beat together after endpoint changes.

Authenticated URIs must identify the authentication database through their path or
`authSource`. The logical database name does not change the URI's authentication
database or move database users.

The knowledgebase/identity relocation scripts accept `--source-mongo-uri` and
`--target-mongo-uri`; `--mongo-uri` explicitly selects a shared endpoint for both.
Their default source is the primary endpoint and their default destination is the
appropriate service endpoint. They remain manual, dry-run by default, and require
distinct source/target namespaces plus explicit confirmation for source removal.
Identical database names are supported on distinct replica sets or standalone
processes. A live topology check rejects alias-based self-copy; when separation
cannot be established (for example, different mongos routers), use distinct
destination names or a cluster-aware migration procedure. Stop writers throughout
copy and verification, even when a topology check confirms separate deployments.
Bootstrap accepts `--identity-mongo-uri` and `--knowledgebase-mongo-uri`
independently of its primary `--mongo-uri`. HGNC and VEP reference seeds use
`--knowledgebase-db` or `KNOWLEDGEBASE_DB`; they are not application collections.
See [reference migration](../operations/migrations/knowledgebase-database-migration.md) for
moving existing references and retiring the superseded diagnosis collection.

Capacity snapshots include a logical `service` label, so identically named
databases on separate hosts remain distinguishable without exposing URIs. Index
retirement rejects ambiguous collection names; use `--repository` with the exact
repository identifier from the index plan to select the intended target.

Backup/restore archive commands operate on one MongoDB deployment per invocation.
Back up split deployments separately; a single archive/oplog cannot establish an
atomic point-in-time snapshot across them. See [recovery procedures](../deployment/mongodb-setup-and-recovery.md).
