# Submit a sample from a pipeline

Use this procedure to validate a local sample manifest, upload its files, and wait
for confirmed ingestion. Coyote Relay supplies the commands. For a custom HTTP
integration, use the [ingestion API reference](sample-ingestion.md).

## Before you start

- Install the [Relay submission tools](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/getting-started.md)
  on the pipeline host. In a development checkout, use the environment prepared
  by the [uv development guide](../sdk/uv-development.md).
- Confirm that the destination API has Relay installed and an ingestion worker
  running. The standard application deployment includes both.
- Ask the administrator to complete [assay setup](../administration/assay-setup.md)
  for the manifest's assay, diagnosis and environment.
- Obtain a [managed service credential](sample-ingestion.md#managed-service-credentials)
  scoped to that assay and environment, with **Upload a background sample bundle**
  and **Read status and results of jobs submitted with this token** enabled.
  Store the credential in your pipeline's secret store or a protected file.

The commands below use synthetic paths and an example API address. Replace them
with the intended deployment and input locations. Include the application's URL
prefix, if it has one; do not append `/api/v1`.

## 1. Prepare and validate the input

Create a [sample manifest](../reference/sample-manifest.md) that identifies the
sample and lists its analysis files. The manifest's `assay`, `diagnosis` and
`profile` select its clinical configuration. Each file must follow its
[input format](../reference/ingest-files/README.md).

Validate it on the pipeline host:

```bash
coyote-relay-validate --yaml /path/to/sample/coyote4.yaml --check-files
```

Relative file paths resolve against the manifest's directory. This command checks
the sample contract and declared file existence without submitting anything.
The server still checks access, active assay configuration, required files and
clinical input contents during ingestion. Local validation alone does not confirm
that a sample is ready for review.

## 2. Submit and wait for completion

```bash
coyote-relay-submit /path/to/sample/coyote4.yaml \
  --base-url https://coyote.example.org/center \
  --auth bearer --token-file /run/secrets/coyote-token \
  --async --wait
```

Relay uploads the bundle, saves the accepted job ID in a local receipt, and polls
until the job completes. Keep the manifest and its inputs unchanged during this
process. The manifest directory must be writable so Relay can save its receipt
and acknowledge the result.

For repeated submissions, set `COYOTE_RELAY_API_URL` and `COYOTE_RELAY_AUTH` instead
of repeating the connection arguments. See
[Relay configuration](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/configuration.md) for environment
variables, alternate credential sources and trusted CA settings.

## 3. Check the result

With `--async --wait`, confirmed success returns exit code `0` and renames the
manifest to `coyote4.yaml.done`. A confirmed ingestion failure returns exit code
`1` and renames it to `coyote4.yaml.failed`. The adjacent
`coyote4.yaml.ack.json` receipt retains the acknowledgement and job identity.

Open **Samples** in the application and check the returned sample identity and
its readiness before starting clinical review. A completed ingestion does not
replace clinical review or report approval.

Using `--async` without `--wait` returns after job acceptance. Its exit code `0`
does **not** mean the clinical writes have completed, and the manifest is not yet
renamed.

## If the job is interrupted or fails

| Situation | Next action |
| --- | --- |
| Polling times out or the connection drops after acceptance | Keep the receipt and unchanged manifest. Repeat the same `--async --wait` command with the same valid credential to resume the accepted job. |
| The credential expires or is revoked | Ask an authorized operator to inspect the saved job; a different credential cannot assume ownership of its status requests. |
| The job returns a validation error | Read the reported file, field or configuration error. Correct it through the normal input/configuration workflow and follow the recovery procedure before submitting again. |
| It is unclear whether the upload was accepted | Keep the receipt and investigate the recorded job or request. Do not delete the receipt to force another upload. |

Use [ingest job recovery](../operations/ingest-job-recovery.md) for reconciliation
and safe retries. Use [ingestion error details](sample-ingestion.md#diagnosing-ingestion-failures)
to locate the relevant response, notification and audit information.
