# Usage

The installer reads the reviewed demonstration environment. Its MongoDB
credentials must have privileges limited to the four demo databases. Supply an
existing demonstration administrator as the installation actor.

Plan starter configuration and synthetic DNA/RNA samples:

```bash
coyote-demo-install --actor demo.admin --starter
```

Install the plan:

```bash
coyote-demo-install --actor demo.admin --starter --apply
```

Omit `--starter` to plan or install configuration alone. `--mongo-uri` and `--db`
override the primary endpoint/name, but all isolation checks still apply.
Commands do not load a local environment file automatically.

The optional API retains these routes and requires an authenticated session with
`demo:install`; browser writes also retain the host's CSRF protection:

- `GET /api/v1/admin/demo-installation`
- `POST /api/v1/admin/demo-installation/starter`
- `POST /api/v1/admin/demo-installation/configuration`
- `POST /api/v1/admin/demo-installation/samples/{key}`

Only packaged sample keys are accepted. Conflicting configuration is rejected;
completed starter samples can be retained when retrying an interrupted install.
Reviewed or human-owned samples are never replaced.

Run all three background services with the `worker` extra installed:

```bash
python -m coyote_demo.runtime ingest --concurrency=1
python -m coyote_demo.runtime maintenance --concurrency=1
python -m coyote_demo.runtime beat
```

Use separate processes. Each command validates target settings and MongoDB
credential scope before starting. Workers accept a positive `--concurrency` and
all services accept `--loglevel`; broker, queue and scheduler paths come from the
reviewed demo configuration. Beat schedules the normal ingest dispatch, audit,
report and maintenance work. Directory watching remains disabled in generated
demo settings. The repository's native and Docker launchers provide these same
services without loading an ordinary deployment environment.
