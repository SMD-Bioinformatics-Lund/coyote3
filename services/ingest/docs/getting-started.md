# Getting started

The submission tools require a POSIX environment, such as Linux or WSL, and Python
3.12 or newer. Install reviewed release wheels from
your deployment's artifact directory; public package publication is separate.

```bash
python -m pip install --no-index --find-links /path/to/wheels coyote-ingest==1.0.0
coyote-ingest-validate --help
coyote-ingest-submit --help
```

The base installation uses `coyote-core` and `coyote-pyclient`. It does not require
the server, MongoDB driver or Celery. Submission uses `curl`; optional remote
manifest retrieval also needs `ssh` and `scp`. A base install can validate input
and submit through an API, but cannot directly access the application's database.

Install the worker extra on the application host:

```bash
python -m pip install --no-index --find-links /path/to/wheels 'coyote-ingest[worker]==1.0.0'
coyote-ingest-worker --loglevel INFO
```

Configure this process with the same reviewed server environment, database
endpoints and mounted ingestion paths as the API. The worker extra installs
`coyote-server`; it reuses its runtime composition and MongoDB adapter. Beat and
maintenance workers remain separate server processes.

When upgrading from server-owned ingestion tasks, pause producers, drain the old
ingestion worker and queue, then deploy the coordinated API, beat and ingestion
worker release. Existing durable jobs retain their identifiers and recovery
receipts. The new worker does not accept old task-name aliases.
