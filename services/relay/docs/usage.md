# Usage

Validate a synthetic manifest before submitting it:

```bash
coyote-relay-validate --yaml /path/to/sample/coyote4.yaml --check-files
coyote-relay-submit --help
```

Validation checks the core sample contract. Relative paths resolve against the
manifest directory. `--check-files` verifies file existence; `--list-files` prints
resolved declared input paths. Validation does not authenticate or write data.

Use `coyote-relay-login --help` for supported login modes. Prefer a password
environment variable over a literal command-line password. Session metadata hides
the token unless `--print-token` is explicitly requested.

Configure one destination for login and submission through the environment:

```bash
export COYOTE_RELAY_API_URL=https://coyote.example.org/center
export COYOTE_RELAY_AUTH=bearer
coyote-relay-login --mode token --token-file /run/secrets/coyote-token
coyote-relay-submit /path/to/sample/coyote4.yaml \
  --token-file /run/secrets/coyote-token --async --wait
```

Or select the destination and an existing pipeline credential explicitly:

```bash
coyote-relay-submit /path/to/sample/coyote4.yaml \
  --base-url https://coyote.example.org/center \
  --auth bearer --token-env PIPELINE_API_TOKEN --async --wait
```

The token must already be supplied through the selected file or environment
variable. Command-line connection values override the corresponding environment
values; see [configuration](configuration.md) for all supported variables.

With `--async --wait`, submission retains its local receipt and polls the accepted durable job before
acknowledging success. A successful upload response alone does not prove that the
clinical writes completed. Retry an interrupted submission using the same input
and receipt so accepted work is recovered instead of submitted again. Do not
modify a manifest after submission.

The configured directory watcher runs through beat and the ingestion worker. It
retains a durable job before executing a stable manifest, and renames the manifest
only after confirmed completion. Busy, disabled and retryable jobs remain for a
later scan. Changed manifests are left untouched. A failed acknowledgement does
not undo committed data; a later scan uses the stored job result.

The worker revalidates managed service credentials at execution time. Original
submitter attribution, scope checks, fenced leases and transactional completion
remain part of the core/server execution path.
