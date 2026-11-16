# Getting started

The submission tools require a POSIX environment, such as Linux or WSL, and Python
3.12 or newer. Install reviewed release wheels from
your deployment's artifact directory; public package publication is separate.

```bash
python -m pip install --no-index --find-links /path/to/wheels coyote-relay==1.0.0
coyote-relay-validate --help
coyote-relay-submit --help
```

The base installation uses `coyote-core` and `coyote-pyclient`. It does not require
the server, MongoDB driver or Celery. Submission uses `curl`; optional remote
manifest retrieval also needs `ssh` and `scp`. A base install can validate input
and submit through an API, but cannot directly access the application's database.

Configure the target API through the environment or command-line options:

```bash
export COYOTE_RELAY_API_URL=https://coyote.example.org
export COYOTE_RELAY_AUTH=bearer
# Supply COYOTE_RELAY_TOKEN through your protected environment or a token file.
coyote-relay-submit --help
```

Command-line options take precedence. See [configuration](configuration.md) for
credential sources and TLS settings, and [usage](usage.md) for submission examples.

## API integration

Install Relay into the same Python environment as the API:

```bash
python -m pip install --no-index --find-links /path/to/wheels 'coyote-relay[api]==1.0.0'
```

Restart the API through your normal deployment procedure. It discovers Relay's
installed `coyote.api.routers` entry point and includes sample, collection and job
endpoints in `/api/v1/docs`, `/api/v1/redoc` and `/api/v1/openapi.json`. Existing
authentication, permissions, assay/environment scope and CSRF checks still apply.
The standard application image includes Relay. Without Relay installed, these
routes are absent from both the API and its schema.

Installation does not start a worker. Synchronous submissions run through the API;
background submissions require the worker process below.

## Worker integration

Install the worker extra on the application host:

```bash
python -m pip install --no-index --find-links /path/to/wheels 'coyote-relay[worker]==1.0.0'
coyote-relay-worker --loglevel INFO
```

Configure this process with the same reviewed server environment, database
endpoints and mounted ingestion paths as the API. The worker extra installs
`coyote-server`; it reuses its runtime composition and MongoDB adapter. Beat and
maintenance workers remain separate server processes.

When upgrading from server-owned ingestion tasks, pause producers, drain the old
ingestion worker and queue, then deploy the coordinated API, beat and ingestion
worker release. Existing durable jobs retain their identifiers and recovery
receipts. The new worker does not accept old task-name aliases.
