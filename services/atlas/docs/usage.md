# Usage

## Offline review

```bash
coyote-atlas inspect
coyote-atlas validate
coyote-atlas plan
```

`inspect` reads the manifest. `validate` checks every resource hash, file size,
record count, collection contract and diagram reference. `plan` performs the
same checks and returns the bundle identity and logical target counts. No
command above opens a database or network connection.

For a separately supplied local pack, put `--bundle /path/to/reference` before
the command. Its manifest and complete file inventory must pass the same checks.
This option never uploads local data or asks the server to read a client path.

## Explicit installation

First review `coyote-atlas plan` and retain its `manifest_sha256`. Configure the
API URL and an administrator session token through the documented environment
variables. Then request that exact installed bundle:

```bash
coyote-atlas install --expected-manifest-sha256 REVIEWED_SHA256
```

The CLI checks the local digest and the server checks its own installed bundle.
A mismatch returns a conflict without installation. To inspect the server's
bundle and current empty target collections, use
`GET /api/v1/admin/references/plan` in the authenticated API reference.

An authenticated `admin`, `sys_admin` or `superuser` session with no outstanding
password change is required. Ingestion tokens cannot install reference data.
The server's normal CSRF protection applies to browser-cookie requests; the CLI
sends the selected bearer token using HTTPX with TLS verification enabled.

Populated collections are normally skipped. `--force` explicitly requests the
existing controlled repair of bundled records; it is not a database replacement.
Center-managed or externally published reference content retains the host's
preservation protections. Review the returned collection statuses.

If a request times out, its outcome is unknown. Inspect the server's audit and
reference publication state before retrying. Atlas adds no automatic retry,
background refresh or database migration.
