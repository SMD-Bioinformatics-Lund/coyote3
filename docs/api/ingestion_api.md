# Ingestion API

## Authorization and write boundaries

User-authenticated ingest routes require `internal.ingest:manage`. Sample-bundle operators also
need `sample:edit:own` for the manifest's assay and environment. Non-superuser
requests must supply both `asp_id` and `environment`. Ingest updates cannot
change a sample's assay or environment; use sample administration for scope changes.

The synchronous sample-bundle JSON and upload routes additionally accept
`X-Coyote-Internal-Token`, using the deployment's existing `INTERNAL_API_TOKEN`.
This creates a request-scoped `internal-ingest` machine identity, not a user
account or session. It can ingest active assays in the deployment's `ENV_NAME`
environment, including explicitly requested sample updates. It cannot use user
administration, arbitrary collection ingestion, asynchronous submission, or task
status routes. Missing/invalid tokens fail authentication; browser user sessions
retain their existing RBAC and assay scope checks.

Direct identity and clinical collection imports are superuser-only because raw
inserts and replacements bypass the dedicated account and clinical workflows.
This restriction applies to synchronous, uploaded, bulk, and queued operations.
Use account administration to manage users, roles, and permission policies.
The supported-collections endpoint lists only collections backed by the configured
ingest gateway and a validation contract. Governed rule/catalog workflows are not
available through generic collection ingestion.

ZIP bundles are validated before extraction. Duplicate normalized paths, file/directory
collisions, traversal paths, symlinks, and existing extraction targets are rejected.

## Purpose

Use the API to load configuration data and sample bundles in a validated, repeatable way.

For an end-to-end relationship map of `asp`/`aspc`/`isgl` with `samples`, `variants`, `cnvs`, and RNA collections, see [Product / DNA And RNA Workflow Chain](../product/workflow_dna_rna.md).
For full per-collection key contracts (required and optional), see [API / Collection Contracts](collection_contracts.md).
For the sample ingest manifest shape used by these routes, see [API / Sample YAML Guide](sample_yaml.md).
For the raw VCF and JSON file shapes consumed by the ingest parsers, see [API / Sample Input Files](sample_input_files.md).

All ingest endpoints validate request documents with backend Pydantic contracts before any database write. Payloads are normalized before persistence, so the behavior is the same whether the caller is a script or an API client.

![Celery-backed sample ingest flow](../assets/diagrams/celery_ingest_flow.svg)

## Persistence and recovery boundaries

For fresh sample creation through:

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/sample-bundle/upload`

the ingest flow follows this order:

1. Validate the top-level sample payload.
2. Parse referenced data files into preload payloads.
3. Insert the sample anchor with `ingest_status="loading"`.
4. Write dependent finding and quality collections (`variants`, `cnvs`, `fusions`, `panel_coverage`, and related evidence).
5. Mark the sample as `ingest_status="ready"` only after all dependent writes succeed.

Failure behavior:

- If validation or file parsing fails, no sample document is inserted.
- The sample anchor, dependent evidence, and ready state commit in one required MongoDB transaction. A failed transaction exposes none of its writes; there is no unprotected-write fallback or compensating deletion.
- A replica set or sharded cluster is required, including for local development.

Scope note:

- `update_existing=true` changes metadata and replaces declared evidence in one transaction. Evidence not declared in the update is retained. A concurrent sample change detected after preparation rejects the update rather than overwriting it.
- Async ingestion commits its job completion receipt in the same transaction as the data. File parsing occurs before the transaction; cache invalidation and file cleanup occur after commit.
- See [transactions and ingest recovery](../architecture/transactions_and_ingest_recovery.md) for delivery, retry, file-retention, and deployment requirements.

## Endpoints

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/sample-bundle/async`
- `POST /api/v1/internal/ingest/sample-bundle/upload`
- `POST /api/v1/internal/ingest/sample-bundle/upload/async`
- `POST /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/async`
- `POST /api/v1/internal/ingest/collection/bulk`
- `POST /api/v1/internal/ingest/collection/bulk/async`
- `PUT /api/v1/internal/ingest/collection`
- `PUT /api/v1/internal/ingest/collection/async`
- `POST /api/v1/internal/ingest/collection/upload`
- `GET /api/v1/internal/ingest/collections`
- `GET /api/v1/internal/tasks/{task_id}`
- `GET /api/v1/internal/metrics`

## Celery-backed async ingest

The async routes perform the same API authentication and authorization checks as
the synchronous internal ingest routes, persist an `ingest_jobs` record, and then
publish its identifier to the Celery `ingest` queue. Acceptance means the job is
durably recorded, not that ingestion has completed. Beat redelivers pending jobs
and expired leases every 30 seconds. Every Compose environment uses the stable
`worker` service key.

Runtime settings:

- `CELERY_WORKER_CONCURRENCY`: Worker concurrency. Defaults to `2`.
- `/data/coyote3_<env>/ingest_staging`: Fixed durable server-side staging root for async upload files.

Redis broker/result URLs are internal Compose wiring. They are not center-owned
environment-file settings.

Async response:

```json
{
  "status": "accepted",
  "task_id": "6f3a...",
  "task_name": "api.tasks.ingest.ingest_sample_bundle",
  "queue": "ingest"
}
```

Poll status:

```bash
curl -sS "${BASE_URL}/api/v1/internal/tasks/${TASK_ID}" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}"
```

The async upload route stores the uploaded YAML and ZIP archive contents in a durable staging
directory before recording the job. The worker removes that staging directory
only after confirmed success. Failed jobs retain their payload and staged files
for investigation. Task status is available to its submitter or a superuser and
does not expose the stored source payload, staging path, or lease token.

## Admin ingest workspace

The Admin Ingest Workspace is a UI wrapper around the async upload endpoint.
Operators provide:

- one `coyote3.yaml` / `*.coyote3.yaml` manifest
- one optional ZIP archive containing the files referenced by the manifest
- `update_existing` when the manifest should replace data for an existing sample
- `increment` when a new unique sample name should be generated from the case id

The UI submits multipart form data to:

```text
POST /api/v1/internal/ingest/sample-bundle/upload/async
```

The response returns a Celery `task_id`. The workspace polls:

```text
GET /api/v1/internal/tasks/{task_id}
```

and displays worker state, completion status, errors, and the final ingest result.
This is the supported browser workflow for manual operator-triggered ingestion.

## Remote manifest acknowledgement

Duplicate sample names are checked after parsing and authorizing the YAML, before
ZIP extraction and analysis-file processing. Without `update_existing=true` or
`increment=true`, an existing name fails with instructions to choose one of those
options. Multipart request bytes may already have been received by the HTTP server;
this check avoids ingestion processing, not network transfer. Final name and
database constraints still apply if another request creates a sample concurrently.

### Expiring credentials for unattended uploads

An authenticated user with `ingest.token:issue` can call
`POST /api/v1/admin/ingest-tokens` with `{"expires_hours": 24}`. Assign this
permission explicitly through your role policy after synchronizing the RBAC
catalog. User bearer sessions or browser sessions are accepted; browser sessions
also require `X-CSRF-Token`. Internal secrets and ingestion tokens do not authorize
issuance. No Docker command is needed. The pipeline itself needs no user login.

For example, using an authorized user's existing session token:

```bash
umask 077
curl --fail --silent --show-error \
  "${BASE_URL}/api/v1/admin/ingest-tokens" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data '{"expires_hours":24}' > ingest-credential.json
export COYOTE3_INGEST_TOKEN="$(python3 -c 'import json; print(json.load(open("ingest-credential.json"))["token"])')"
```

The response includes `token`, `token_id`, `expires_at`, `environment`, `scope`,
and `header`, with `Cache-Control: no-store`. Save it securely: there is no token
retrieval endpoint. Issuance records the authenticated issuer, credential ID,
scope, and expiry in the audit, never the credential value. If the audit cannot
be persisted, issuance fails without returning a token.

Use `--auth ingest` with `scripts/submit_ingest_manifest.py`, or send the token in
`X-Coyote-Ingest-Token`. Keep the file private. The token can be reused until its
expiry (default 24 hours, maximum 720 hours); it is not a single-use token. Issue
a replacement before expiry for scheduled pipelines. Its audit identity includes
a unique token identifier. It is limited to synchronous sample-bundle ingestion
in the environment where it was issued; async and task endpoints require user
authentication. Other administrative endpoints do not accept it.

Issuing a new token does not revoke older tokens. Rotating `INTERNAL_API_TOKEN`
and recreating the API invalidates all tokens signed with the previous secret
and affects other clients using that internal secret. Individual token revocation
is not implemented. Distribute the expiring token, not the signing secret.

The token's environment identifies the API deployment accepting the request,
not the sample profile in the YAML. A development API can ingest a manifest with
`profile: production` to test production analysis configuration. The manifest's
profile is preserved; database connections come from the deployment settings.
The token remains invalid on a different deployment environment. User-session
uploads retain their existing role and sample-scope checks.

### Built-in directory watcher

The Celery beat schedule dispatches the ingestion watcher when
`COYOTE3_INGEST_WATCH_ENABLED=1`. A worker scans the mounted ingest watch directory
for `COYOTE3_INGEST_WATCH_FILENAME` (default `coyote3.yaml`), registers durable jobs,
with scans scheduled by `COYOTE3_INGEST_WATCH_INTERVAL_SECONDS` (default 30 seconds),
and invokes ingestion directly. It does not call the upload API and uses no HTTP
token. Its audit identity is `ingest-watcher`. Successful jobs rename the manifest
with the done suffix; nonretryable failures use the failed suffix. Retryable or
busy jobs remain available for a later scan. The worker needs filesystem access
to the manifest and data, plus directory write permission for acknowledgement.
Use the deployment-server SCP helper when files are only available remotely.
For development the container watch path is
`/data/coyote3_dev/copied_sample_files/yaml`; with `/data/coyote3:/data`, its host
path is `/data/coyote3/coyote3_dev/copied_sample_files/yaml`.

### Deployment-server helper

Run `scripts/submit_ingest_manifest.py` on the deployment server. Use
`--remote-host USER@ANALYSIS_SERVER` to fetch the YAML and optional ZIP with SCP,
submit them to the API, then rename the original YAML through SSH after a terminal
acknowledgement. SCP cannot rename remote files; SSH command access is required.
The helper requires Python 3.10+, `curl`, `ssh`, and `scp` on the deployment server;
it has no Coyote3 Python package or MongoDB dependency. The analysis server needs
a POSIX shell and `sha256sum`, `ln`, and `rm`, but no installed helper or API token.
Configure SSH key/agent access and verified host keys beforehand. The SSH account
must be able to read the inputs and modify their directory. Remote paths must be
absolute, without spaces or shell metacharacters.

By default the helper reads `INTERNAL_API_TOKEN` and sends the internal
header, so unattended pipelines do not log in. Use the same secret value as the
target deployment's private env file; do not generate a different client token.

```bash
read -rsp 'Internal API token: ' INTERNAL_API_TOKEN; echo
export INTERNAL_API_TOKEN
python3 scripts/submit_ingest_manifest.py /pipeline/outgoing/sample.yaml \
  --remote-host pipeline@analysis.example.org \
  --base-url https://coyote.example.org/coyote3_dev \
  --archive /pipeline/outgoing/sample.upload.zip
```

Include the application path prefix in `--base-url`, but not `/api/v1`.
For cron or a pipeline service, supply `INTERNAL_API_TOKEN` through its protected
environment/secret configuration instead of prompting. Do not put the value in
the command line or commit it. Existing user session tokens remain supported
with `--auth bearer` and `API_BEARER_TOKEN`.

Check connectivity without any credentials before submitting:

```bash
curl --fail --show-error --silent --max-time 15 \
  https://coyote.example.org/coyote3_dev/api/v1/health
```

The expected response is `{"status":"ok"}`. This lightweight endpoint checks API
reachability, not all database permissions or ingest readiness. Configure a trusted
CA bundle if needed; do not disable certificate verification.

Alternatively set `COYOTE3_BASE_URL`. Omit `--archive` when every required
input path in the YAML is already readable inside the API container. A YAML
upload alone does not transfer its referenced data. ZIP entries must match the
manifest paths or have unique matching basenames, as for the UI upload.

The script uses the synchronous endpoint below and appends the outcome to the
original filename: `sample.yaml.done` for `status=ok`, or `sample.yaml.failed`
for `status=failed`. In remote mode, it saves the full reason/result in a hashed
`.ack.json` file under `~/.local/state/coyote3-ingest` on the deployment server
(`$XDG_STATE_HOME/coyote3-ingest` when set). Use `--state-dir` to select another
durable directory. Receipts have owner-only permissions and are saved before the
remote rename. A hash check prevents acknowledging a YAML changed since upload.
Both statuses leave the input ZIP untouched; downloaded temporary copies are removed.
A local state lock prevents competing submissions from this deployment server.
Run one coordinator for each remote manifest and retain its receipt directory.

Without `--remote-host`, inputs are local: the receipt is `sample.yaml.ack.json`
and the lock is `sample.yaml.submit.lock` beside the YAML.

Exit codes:

| Code | Result | Original manifest |
| --- | --- | --- |
| `0` | API acknowledged success | `.done` appended |
| `1` | API acknowledged ingest failure | `.failed` appended |
| `2` | Transport, HTTP, invalid response, or finalization error | Finalization unconfirmed; inspect the receipt and diagnostic |

Use `--timeout SECONDS` (default 1800) for the complete request, and `--ca-bundle`
for a center CA certificate. Certificate verification remains enabled. Proxy
timeouts still apply independently. `--update-existing` and `--increment` pass
the corresponding ingest options to the API.

There are no automatic upload retries. A connection failure or timeout can occur
after the API commits: inspect the application audit before resubmitting an
unacknowledged input. Do not blindly retry exit code 2 from cron. When a terminal
receipt exists but the YAML rename failed, rerunning the same command completes
the rename without uploading again, provided the YAML hash, API URL, and remote
location still match. This also handles a lost SSH response after a completed rename.
Existing `.done` and `.failed` files are never overwritten. After
correcting an acknowledged failure, archive the previous receipt and failed
manifest before submitting the corrected YAML under its original name.

Use the synchronous upload endpoint with `acknowledge=true` when a remote
pipeline owns the manifest directory and the application may only read it. The
caller uploads the YAML, receives a terminal JSON response, and is responsible
for writing its own acknowledgement file or renaming the manifest.

When the paths in the YAML are readable by the API container, no archive is
required:

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/sample-bundle/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "yaml_file=@/pipeline/outgoing/coyote3.yaml;type=text/yaml" \
  -F "acknowledge=true"
```

The response is always a terminal acknowledgement for ingest validation or
write failures handled by the route:

```json
{
  "status": "ok",
  "sample_name": "example_sample",
  "sample_id": "…",
  "message": "Sample bundle ingested successfully",
  "result": { "written": { "variants": 12 } }
}
```

or:

```json
{
  "status": "failed",
  "sample_name": null,
  "sample_id": null,
  "message": "Missing declared files for YAML references: …",
  "result": null
}
```

Authentication and authorization failures still use their normal HTTP status
codes. A caller should write its own `.done` or `.failed` marker only after
checking the acknowledgement `status`.

## Folder watcher ingest

Compose also defines the stable `beat` scheduler service. When
`COYOTE3_INGEST_WATCH_ENABLED=1`, beat periodically enqueues
`api.tasks.ingest.ingest_watch_directory_once`, which scans
the fixed `/data/coyote3_<env>/copied_sample_files/yaml` directory for `coyote3.yaml`.

Watcher settings:

- `/data/coyote3_<env>/copied_sample_files/yaml`: fixed root folder scanned recursively.
- `COYOTE3_INGEST_WATCH_FILENAME`: manifest filename. Defaults to `coyote3.yaml`.
- `COYOTE3_INGEST_WATCH_INTERVAL_SECONDS`: beat interval. Defaults to `30`.
- `COYOTE3_INGEST_WATCH_UPDATE_EXISTING`: pass `allow_update=true` to sample ingest.
- `COYOTE3_INGEST_WATCH_INCREMENT`: pass `increment=true` to sample ingest.
- `COYOTE3_INGEST_DONE_SUFFIX`: success marker suffix. Defaults to `.done`.
- `COYOTE3_INGEST_FAILED_SUFFIX`: failure marker suffix. Defaults to `.failed`.

The base Compose deployment mounts `COYOTE3_DATA_HOST_ROOT` only at `/data`.
Absolute manifest paths must be readable at the same container location by the API
and worker; host paths are not automatically mirrored. Configure any additional
input mounts in a [private storage override](../operations/deployment_guide.md#center-storage-mounts).
Resolved paths are persisted in `samples.files.<key>.path`. Relative manifest paths
and absolute `/data/...` paths are also supported.

Pipeline identity fields are normalized before any ASP/ASPC lookup:

| Pipeline field | Internal field | Notes |
| --- | --- | --- |
| `assay` | `asp_id` | Normalized to the canonical lowercase ASP identifier. |
| `subpanel` | `subpanel_id` | Normalized to the canonical lowercase subpanel identifier. |
| `profile` | `environment` | Normalized as the environment identifier. |
| `sequencing_technology` | `platform` | Normalized against configured platform values. |

Supplying both names is allowed only when their values agree. All internal
services use only the right-hand canonical field names after this boundary.

Relative file paths inside each manifest are resolved from that manifest's
directory. After successful ingest, the watcher renames the manifest to
`coyote3.yaml.done`; failed manifests are renamed to `coyote3.yaml.failed` so
they do not loop continuously.

The success marker records completion of the required bundle workflow: the sample and
every declared analysis resource have been validated, persisted, and marked
`ready`. Optional public knowledgebase enrichment is queued only after that
marker is written. A slow or unavailable external service cannot hold the
watch-folder lock, leave a successful manifest pending, or turn a ready sample
into a failed ingest.

The watcher is protected by a non-overlap lock. If a previous scan is still
parsing or writing a sample bundle when the next beat tick fires, the newer task
returns `skipped` with `reason=already_running` and does not touch any manifest
files.

If the ingest family is disabled while a scan is in progress, its durable job and
manifest are preserved for a later enabled run. A disabled or busy result produces
neither a success marker nor a success audit event. A `.done` acknowledgement follows
successful processing, including recovery of an already-committed receipt.

### Ingest load validation

The [optional load-testing workflow](../testing/load_testing.md) treats ingest as an
explicit opt-in write workload using sample JSON and a small synthetic biomarker file.
It measures dispatch, biomarker parsing, and persistence, not staged uploads or
large-file throughput. Use a dedicated synthetic ASP/ASPC configured for that input;
do not weaken clinical assay requirements.
Record request acceptance latency separately from time to terminal job status and
sample readiness. Include failed jobs, queue wait, timeouts, and post-load drain time;
a fast acceptance response does not demonstrate ingest throughput. Disable or mock
external enrichment so workers do not direct test traffic at third-party services.

## MongoDB dependency

API and workers use independent app, identity, knowledgebase, and BAM endpoints.
Sample ingestion and its job receipts stay on the primary endpoint. Async raw
collection ingestion returns HTTP 400 when its target uses a different client;
use synchronous ingestion or maintenance tooling for that target. Synchronous
writes use the selected collection's client, never a session from another service.
See [MongoDB service topology](../architecture/mongodb_topology.md).

## Route commands (full examples)

Set runtime variables once:

```bash
export BASE_URL="http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}"
# Option A: existing bearer token
export API_BEARER_TOKEN="<YOUR_API_BEARER_TOKEN>"

# Option B: login via CLI helper
${PYTHON_BIN:-python} scripts/api_login.py \
  --base-url "${BASE_URL}" \
  --mode password \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --print-token
```

For a new empty database, run the direct bootstrap command before starting the
application services:

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$COYOTE3_MONGO_URI" \
  --identity-mongo-uri "$IDENTITY_MONGO_URI" \
  --db "$COYOTE3_DB" \
  --identity-db "$IDENTITY_DB" \
  --sys-admin-username "center.operator" \
  --sys-admin-email "operator@example.org" \
  --username "admin.coyote3" \
  --email "admin@your-center.org" \
  --password "<GENERATED_ADMIN_PASSWORD>"
```

Behavior:

- It creates the first local superuser and loads `permissions`, `roles`,
  `hgnc_genes`, and `vep_metadata` only into empty collections.
- It rejects a partially initialized identity database rather than merging
  uncertain state.
- Add `--with-demo-center` only to load the repository's synthetic ASP, ASPC,
  and ISGL demonstration documents in a nonclinical environment.

Seed source policy for a new deployment:

- The application-owned RBAC catalog is `api/config/bootstrap/rbac`. It installs
  every bundled permission policy and built-in role only during explicit
  direct bootstrap or explicit catalog synchronization.
- `api/config/bootstrap/demo_center` provides synthetic ASP, ASPC, and ISGL
  records for installation verification. Replace these with reviewed center
  definitions before clinical use.
- HGNC and VEP metadata are bundled release snapshots. The bootstrap command
  loads them only when the target collection is empty; it never takes data from
  test fixtures.
- Keep center seed changes deterministic and version-controlled in the center's
  private deployment configuration.
- `asp_configs` documents are contract-driven and must carry typed `filters`,
  `analysis_types`, and `reporting` objects. Query behavior is derived from those
  typed sections and the domain query builders; arbitrary top-level Mongo query
  overrides are not part of the supported ingest contract.
  CNV behavior is configured with `filters.cnv_*` keys.
  Fusion behavior is configured with `filters.fusion_*` keys.

Validate assay consistency before ingesting sample bundles:

```bash
${PYTHON_BIN:-python} scripts/validate_assay_consistency.py \
  --seed-file api/config/bootstrap/demo_center \
  --yaml demo_data/ingest/generic_case_control.yaml
```

The DNA demo YAML intentionally omits `database_versions`. DNA VCF ingest
captures the curated `database_versions` snapshot from the `##VEP=` header.
The manifest may provide `database_versions` only as an explicit override or
supplement; a supplied value takes precedence for its matching key. The stored
keys are limited to `assembly`, `clinvar`, `cosmic`, `dbsnp`, `ensembl`,
`gencode`, `genebuild`, `gnomad`, `hgmd_public`, `polyphen`, `sift`, and `vep`.

DNA ingest writes two coordinated records and one compact query index for each
small variant:

- The sample-local variant row stores only the clinical display anchor in
  `INFO.selected_CSQ` and `consequence_terms`, the ordered union of all VEP
  consequence terms for the variant.
- The global `anno_vep` vault stores all parsed transcript summaries by
  `simple_id_hash` and `vep_version`.

> **Info: Transcript vault**
>
>
> `anno_vep` is version tagged. A manual transcript change for a variant
> reads from the exact VEP version recorded on the sample and then updates the
> sample-local display anchor. This keeps transcript switching deterministic
> across VEP releases while keeping the variant table compact.
>
> The vault key is `(simple_id_hash, vep_version)`. A repeated ingest for the
> same identity and release is an insert no-op and cannot replace existing
> evidence. Ingesting the same identity with another VEP release writes a
> separate vault document, and each sample reads its own recorded release.
>

The selected anchor is deliberately compact. It retains display fields such as
the transcript feature, normalized gene and HGNC identifiers, HGVS,
consequence, impact, prediction values, and exon/intron. Raw MANE and
canonical VEP fields remain in `anno_vep.CSQ[]`. Current HGNC match state and
transcript badges are generated only when a transcript detail payload is read.

Small-variant consequence filters query `variants.consequence_terms`. They do
not query `INFO.selected_CSQ.Consequence` or the VEP vault at request time, so
changing the selected display transcript does not change the filterable term
set.

Every transcript summary in `anno_vep.CSQ` is validated by the
`VepAnnoTranscriptDoc` contract. It stores VEP fields used for review
(`Feature`, `HGVSc`, `HGVSp`, `Consequence`, `IMPACT`, `EXON`, `INTRON`,
`SIFT`, `PolyPhen`, and `CADD_PHRED`) exactly as versioned annotation evidence.
The API derives NCBI/Ensembl MANE and VEP-canonical display badges against the
current HGNC collection when a reviewer opens a variant detail page.

SIFT, PolyPhen, CADD, and related prediction values are transcript-level VEP
outputs, so they are versioned with the transcript consequence row in
`anno_vep.CSQ[]` rather than duplicated into a separate collection. The sample
document stores the source-version snapshot under `samples.database_versions`
for `sift`, `polyphen`, `vep`, and the other configured reference databases.

Manual transcript selection is exposed through:

Automatic selected-transcript priority is deterministic:

1. NCBI/RefSeq MANE Plus Clinical
2. Ensembl MANE Plus Clinical
3. NCBI/RefSeq MANE Select
4. Ensembl MANE Select
5. VEP canonical protein-coding transcript
6. first protein-coding transcript
7. first available transcript

Within each priority, consequences are considered in `HIGH`, `MODERATE`, `LOW`,
then `MODIFIER` impact order. HGNC ID is the primary gene identity; approved,
previous, and alias symbols are lookup paths to the same HGNC record.

```http
PATCH /api/v1/samples/{sample_id}/small-variants/{var_id}/selected-transcript
```

Request body:

```json
{
  "feature_id": "ENST00000359995"
}
```

The endpoint requires small-variant management permission and returns the
standard sample-change payload used by the UI to refresh the detail view.

This validator checks:

- assay references across `samples`, `blacklist`, `insilico_genelists`
- seed document contract shape (`*.json` arrays of objects only)
- metadata field typing (`created_on`/`updated_on` ISO-8601 strings, numeric `version`)
- rejection of Mongo Extended JSON wrappers (`$date`, `$oid`) in seed files
- required baseline governance/config presence (`roles`, `permissions`)
- `asp_configs` (`aspc_id` format, assay/environment consistency)
- `insilico_genelists` (`asp_ids` and `asp_groups` consistency)
- bootstrap dependencies (`roles -> permissions`, `users -> roles`)

Discover supported collection-ingest contracts:

```bash
curl -sS "${BASE_URL}/api/v1/internal/ingest/collections" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}"
```

### 1) Seed one collection document

Route:

- `POST /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "document": {
    "aspc_id": "assay_1_base_production",
    "asp_id": "assay_1",
    "subpanel_id": "base",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["SNV", "CNV"],
    "display_name": "assay_1 production",
    "filters": {
      "somatic": {
        "snv": {
          "min_freq": 0.05,
          "max_freq": 1.0,
          "max_control_freq": 0.05,
          "max_popfreq": 0.01,
          "min_depth": 100,
          "min_alt_reads": 5,
          "vep_consequences": [],
          "snvlists": []
        },
        "cnv": {
          "min_cnv_size": 100,
          "max_cnv_size": 50000000,
          "cnv_loss_cutoff": -0.3,
          "cnv_gain_cutoff": 0.3,
          "cnveffects": ["gain", "loss"],
          "cnvlists": []
        }
      }
    },
    "reporting": {
      "report_sections": ["SNV", "CNV"],
      "report_header": "assay_1 Report",
      "report_method": "Standard analysis",
      "report_description": "Validated reporting profile",
      "clinical_rule_set_id": "assay_1__base__sv",
      "plots_path": "reports/plots",
      "report_folder": "reports/output"
    },
    "is_active": true
  }
}
JSON
```

For a DNA ASPC, `filters.somatic` contains only the enabled DNA analysis
profiles. `filters.germline.snv` is required only when `analysis_intents`
includes `germline`. RNA ASPCs instead use `filters.somatic.fusion`. Each
enabled `SNV`, `CNV`, `TRANSLOCATION`, `COVERAGE`, or `FUSION` analysis type
requires its matching filter profile.

### 2) Seed many documents (bulk)

Route:

- `POST /api/v1/internal/ingest/collection/bulk`

Command:

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "permissions",
  "documents": [
    {
      "permission_id": "sample:read",
      "label": "View samples",
      "category": "Sample Management",
      "description": "View samples available within the user's access scope.",
      "is_active": true
    }
  ]
}
JSON
```

### 2b) Update or upsert one document

Route:

- `PUT /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X PUT "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "match": {"aspc_id": "assay_1_base_production"},
  "document": {
    "aspc_id": "assay_1_base_production",
    "asp_id": "assay_1",
    "subpanel_id": "base",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["SNV", "CNV"],
    "display_name": "assay_1 production",
    "filters": {
      "somatic": {
        "snv": {
          "min_freq": 0.05,
          "max_freq": 1.0,
          "max_control_freq": 0.05,
          "max_popfreq": 0.01,
          "min_depth": 100,
          "min_alt_reads": 5,
          "vep_consequences": [],
          "snvlists": []
        },
        "cnv": {
          "min_cnv_size": 100,
          "max_cnv_size": 50000000,
          "cnv_loss_cutoff": -0.3,
          "cnv_gain_cutoff": 0.3,
          "cnveffects": ["gain", "loss"],
          "cnvlists": []
        }
      }
    },
    "reporting": {
      "report_sections": ["SNV", "CNV"],
      "report_header": "assay_1 Report",
      "report_method": "Standard analysis",
      "report_description": "Validated reporting profile",
      "clinical_rule_set_id": "assay_1__base__sv",
      "plots_path": "reports/plots",
      "report_folder": "reports/output"
    },
    "is_active": true
  },
  "upsert": true
}
JSON
```

### 2c) Upload collection JSON file (multipart)

Route:

- `POST /api/v1/internal/ingest/collection/upload`

Notes:

- This route validates uploaded JSON via the same collection Pydantic contracts used by
  `/collection`, `/collection/bulk`, and `/collection` upsert.
- For governance/config uploads in admin workflows, supported collections are:
  `users`, `roles`, `permissions`, `asp_configs`, `assay_specific_panels`, `insilico_genelists`.
- `mode=insert` expects a JSON object.
- `mode=bulk` expects a JSON array.
- `mode=upsert` expects a JSON object plus `match_json` form field.

Command:

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "collection=users" \
  -F "mode=insert" \
  -F "documents_file=@/path/to/users.json;type=application/json"
```

### 3) Ingest fresh sample + analysis bundle (YAML string mode)

Route:

- `POST /api/v1/internal/ingest/sample-bundle`

Command (YAML content mode):

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/sample-bundle" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<JSON
{
  "yaml_content": $(${PYTHON_BIN:-python} - <<'PY'
import json
from pathlib import Path
print(json.dumps(Path("demo_data/ingest/generic_case_control.yaml").read_text(encoding="utf-8")))
PY
  ),
  "update_existing": false
}
JSON
```

### 4) Ingest fresh sample + analysis bundle (upload YAML + ZIP archive)

Route:

- `POST /api/v1/internal/ingest/sample-bundle/upload`

Command (multipart upload mode):

```bash
zip -j sample_bundle.zip \
  demo_data/ingest/generic_case_control.final.filtered.vcf \
  demo_data/ingest/generic_case_control.cnvs.merged.json \
  demo_data/ingest/generic_case_control.cov.json \
  demo_data/ingest/generic_case_control.modeled.png

curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/sample-bundle/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "yaml_file=@demo_data/ingest/generic_case_control.yaml;type=text/yaml" \
  -F "data_archive=@sample_bundle.zip;type=application/zip" \
  -F "increment=true" \
  -F "update_existing=false"
```

Rules:

- Keep flat file path values in YAML (`vcf_files`, `cnv`, `cov`,
  `fusion_files`, etc.) as source paths.
- Upload one `.zip` archive using `data_archive`. Every declared YAML file
  must either be available at its original path or resolve to one archive member.
- Matching uses the exact YAML path when it is present in the archive, then a
  unique basename. Ambiguous basenames are rejected.
- Backend stages uploaded files temporarily, parses them, ingests to DB, and removes staged files after request completion.
- The source path in the YAML remains the path stored in MongoDB; staging paths
  are used only for the ingest worker.
- Uploaded runtime files are hashed (`sha256`) and persisted on the sample as `uploaded_file_checksums`.

### 4b) Internal metrics endpoint (Prometheus text format)

Route:

- `GET /api/v1/internal/metrics`

Command:

```bash
curl -sS "${BASE_URL}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

### Dependent analysis writes

Dependent SNV, CNV, fusion, translocation, coverage, biomarker, and profile
writes are internal stages of complete sample-bundle ingestion. They are not a
separate public ingest operation. Submit the full manifest through a sample
bundle endpoint with `update_existing=true` when an existing sample must be
reloaded. This preserves one validation, readiness, rollback, and audit
boundary and prevents a caller from leaving a sample partially refreshed.

## Authentication and authorization

- Ingest/collection internal endpoints require authenticated API user session and RBAC.
- Internal ingest endpoints require the `internal.ingest:manage` permission.
- `update_existing=true` on sample-bundle requires authenticated user with `sample:edit:own` permission.
- The Admin UI ingestion workspace (`/admin/ingest`) uses the same
  `internal.ingest:manage` permission.

The generic collection-ingest routes are intentionally more privileged than
normal resource-management routes. Every collection operation through this
interface requires `internal.ingest:manage`. User, role, permission-policy,
ASP, ASPC, ISGL, and sample-linked collection operations additionally enforce
the corresponding create/edit permission documented in
[Collection Operations and Permissions](collection_operations_and_permissions.md).

Normal administrative routes continue to enforce their resource-specific
permissions, such as `user:create`, `assay.panel:edit`, or
`gene_list.insilico:view`. Possessing one of those narrower permissions does
not authorize arbitrary collection ingestion.

## First-time center bootstrap order

Use this order for a clean deployment at a new center.

1. Provision the MongoDB application user outside Coyote3.
2. Run `scripts/bootstrap_database.py` against the empty application and identity databases.
   - It creates the first superuser and loads `permissions` and `roles` into
     `IDENTITY_DB`, and `hgnc_genes` and `vep_metadata` into `COYOTE3_DB`.
   - Add `--with-demo-center` only for the synthetic ASP, ASPC, and ISGL
     demonstration configuration.
3. Start Coyote3 services.
4. Import approved center ASP, ASPC, and ISGL configuration.
5. Optionally import filtering and annotation knowledgebase collections. The
   collection gateway resolves these destinations in `KNOWLEDGEBASE_DB`, not
   the sample-bearing application database.
   - `civic_genes`, `civic_variants`, `oncokb_genes`, `oncokb_actionable`,
     `brcaexchange`, `iarc_tp53`, `cosmic`, `hpaexpr`
6. Ingest sample data.
   - `POST /api/v1/internal/ingest/sample-bundle` for fresh sample + analysis data
   - `POST /api/v1/internal/ingest/sample-bundle/upload` for fresh sample + uploaded ZIP archive
   - use a complete sample bundle with `update_existing=true` to replace an existing sample's declared analysis data

## Collection bootstrapping via API

Use collection endpoints to seed reference/config data with schema validation.

- Single: `POST /api/v1/internal/ingest/collection`
- Bulk: `POST /api/v1/internal/ingest/collection/bulk`

Use these endpoints after the direct first-deployment bootstrap for controlled
center-owned configuration or optional knowledgebase imports. Do not use them
to recreate the bundled governance and reference baseline on a populated
database. Create additional users through the administrative UI/API.

## Minimum required dataset (baseline)

Use this as the minimum deployment contract:

| Collection | Minimum required keys | Why required |
| --- | --- | --- |
| `permissions` | `permission_id` | RBAC policy definitions |
| `roles` | `role_id`, `level`, `permissions[]` | RBAC role resolution |
| `users` | `username`, `email`, `roles[]`, `environments[]` | Login + authorization subject (the first superuser is created by `bootstrap_database.py`) |
| `asp_configs` | `aspc_id`, `asp_id`, `subpanel_id`, `environment`, `asp_group`, `asp_category`, `analysis_types[]`, `display_name`, `filters{...}`, `reporting{...}`, `is_active`, `version` | Assay+subpanel+environment runtime config |
| `assay_specific_panels` | `asp_id`, `asp_group`, `asp_family`, `asp_category`, `display_name`, `expected_files[]`, `required_files[]`, `is_active` | Assay metadata and declared file requirements |
| `insilico_genelists` | `isgl_id`, `diagnosis[]`, `asp_ids[]`, `asp_groups[]`, `list_type[]`, `genes[]`, `is_active` | In-silico gene-list filtering logic |
| `hgnc_genes` | `hgnc_id`, `hgnc_symbol` | Gene metadata and symbol mapping |

Managed-admin form source:

- For ASP/ASPC/ISGL/users/roles/permissions, admin UI forms use backend-generated schemas from contracts (`api/contracts/managed_ui_schemas.py`).
- ASP, ASPC, and ISGL start at `version: 1`. Each edit writes a successor
  document with the same business identifier and the next version, then retires
  the previous active revision. Users, roles, and permissions instead update in
  place and increment `version`. Neither model stores embedded delta arrays;
  managed mutations are also recorded in audit events.

Assay-group contract:

- `asp_group` is a fixed software taxonomy defined in
  `api/config/assay_groups.py`.
- Allowed values are `tumwgs`, `wts`, `hematology`, `myeloid`, `lymphoid`,
  `solid`, `fusion`, and `pgx`.
- `asp_family` is separate: use `panel-dna`, `panel-rna`, `wgs`, or `wts` for
  sequencing-design classification. `asp_category` is separately `dna` or
  `rna`, and `subpanel_id` identifies the in-silico target subset within the
  selected design panel.
- Centers may register any ASP they need, but each ASP and ASPC must use one
  of the fixed assay groups.
- Adding a group requires a reviewed product release and migration of affected
  clinical records; it is not an admin-side data change.

Other fixed admin/runtime vocabularies:

- `asp_family`:
  - `panel-dna`
  - `panel-rna`
  - `wgs`
  - `wts`
- `asp_category`:
  - `dna`
  - `rna`
- `environment` / sample `profile`:
  - `production`
  - `development`
  - `testing`
  - `validation`
- sample `sequencing_scope`:
  - `panel`
  - `wgs`
  - `wts`
- `auth_type`:
  - `local`
  - `ldap`
- `platform`:
  - `illumina`
  - `pacbio`
  - `nanopore`
  - `iontorrent`
- permission `category`:
  - `Analysis Actions`
  - `Assay Configuration Management`
  - `Assay Panel Management`
  - `Audit & Monitoring`
  - `Data Downloads`
  - `Gene List Management`
  - `Permission Policy Management`
  - `Reports`
  - `Role Management`
  - `Sample Management`
  - `Schema Management`
  - `User Management`
  - `Variant Curation`
  - `Visualization`

## Sample bundle request modes

### YAML content

```json
{
  "yaml_content": "name: seed_sample\nassay: assay_1\nsubpanel: base\nprofile: production\n...",
  "update_existing": false,
  "increment": false
}
```

Use the raw, flat pipeline manifest format documented in the DNA and RNA
manifest sections. The service resolves `assay`, `subpanel`, and `profile` to
the active ASPC for analysis filters and policy snapshots. File acceptance and
mandatory inputs come exclusively from the active ASP's `expected_files` and
`required_files`. ASPC `analysis_types` neither adds required files nor overrides
the ASP file policy. An explicitly empty `expected_files` list accepts no files.

### Uploaded archive

`POST /api/v1/internal/ingest/sample-bundle/upload` accepts one ZIP archive.
The YAML manifest is uploaded separately. Files declared by the manifest but
excluded from the active ASP's expected files are ignored with a warning; they
are not parsed or written as sample analysis data. The async response includes
`warnings`, the ingest workspace displays warning notifications, and the worker
records the warnings in the audit. Required files remain mandatory. Accepted
declared files must still be readable and valid. Archive safety checks remain
in force for the complete ZIP. File paths remain the manifest's declared paths in MongoDB; archive
members are matched by basename while the request is processed.

## Collection insert examples

### Diagnosing ingestion failures

Upload validation failures include their reason in the HTTP response and audit.
For queued jobs, the job status, submitter's notification, and audit include the
failure reason and task ID. The worker log records that task ID and traceback.
JSON errors identify the analysis type, filename, and line/column; empty files
are reported as empty. Schema errors identify the collection, record number,
and invalid field. Fix the reported input or configuration before retrying.

### Admin assay configuration

The ASP creation form includes the required ASP ID. It remains visible and
read-only when editing because existing samples and configurations reference
that identifier. User create/edit forms show assay IDs as checkboxes, filtered
by selected assay groups. Removing a group clears its assay selections when
editing the form; normal permission checks still govern saving access changes.

### Single document

```json
{
  "collection": "permissions",
  "document": {
    "permission_id": "sample:read",
    "label": "View samples",
    "category": "Sample Management",
    "description": "View samples available within the user's access scope.",
    "is_active": true
  }
}
```

### Bulk document

```json
{
  "collection": "permissions",
  "documents": [
    {
      "permission_id": "sample:read",
      "label": "View samples",
      "category": "Sample Management",
      "description": "View samples available within the user's access scope.",
      "is_active": true
    },
    {
      "permission_id": "sample:manage",
      "label": "Manage samples",
      "category": "Sample Management",
      "description": "Create, update, and manage samples within the user's access scope.",
      "is_active": true
    }
  ]
}
```

Core collections typically seeded first:

- `permissions`
- `roles`
- first local superuser via `scripts/bootstrap_database.py`
- `asp_configs`
- `assay_specific_panels`
- `insilico_genelists`
- `hgnc_genes`

## Test fixtures for ingestion

- `demo_data/ingest/*`
- `demo_data/collections/all_collections_dummy` (automated tests only; not a deployment seed)

## Client example (Python)

```python
from pathlib import Path

import httpx

base = "http://localhost:6801"
headers = {"Authorization": "Bearer YOUR_API_BEARER_TOKEN"}

payload = {
    "yaml_content": Path("demo_data/ingest/generic_case_control.yaml").read_text(),
    "update_existing": False,
    "increment": False,
}

response = httpx.post(
    f"{base}/api/v1/internal/ingest/sample-bundle",
    json=payload,
    headers=headers,
    timeout=120.0,
)
response.raise_for_status()
print(response.json())
```

## Troubleshooting by error

| Error fragment | Likely cause | Fix |
| --- | --- | --- |
| `Seed contract-shape errors` | Seed files contain invalid document shape/metadata typing | Keep each collection file as `list[object]`, use ISO-8601 datetimes, numeric `version`, and plain JSON scalar values |
| `Unknown assay references in seed` | Seed collections use assay IDs not present in ASPC/panel/ISGL docs | Align assay IDs across `asp_configs`, `assay_specific_panels`, `insilico_genelists` |
| `Bootstrap dependency errors` | Missing required baseline collection docs or broken refs | Populate required collections in onboarding order |
| `Assay config not found for sample` | `asp_configs` doc missing, inactive, or mismatched ASP/subpanel/environment | Ensure the active ASPC has the matching `asp_id`, `subpanel_id`, and `environment`, then keep the manifest `assay`, `subpanel`, and `profile` aligned |
| `No DB document model registered` | Unsupported collection name in ingest request | Use `/api/v1/internal/ingest/collections` and correct `collection` |
| `diagnosis must include at least one value` | ISGL payload missing diagnosis | Provide non-empty `diagnosis` list/string |
| `aspc_id environment segment must match environment` | `aspc_id` and `environment` mismatch | Use the center ASPC identifier format and keep `environment`, `asp_id`, and `subpanel_id` aligned with the document identity |
| `403 Forbidden` on update mode | User missing `sample:edit:own` permission | Add `sample:edit:own` to an assigned role |
