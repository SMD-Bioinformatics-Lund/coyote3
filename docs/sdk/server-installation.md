# Core, server, ingestion service and client installations

Packages are built locally; public-index publication is not required.

| Installation | Contents |
| --- | --- |
| `coyote_core` wheel | Clinical core and its own dependencies |
| `coyote_server` wheel | API, maintenance workers and MongoDB adapter; requires the selected core |
| `coyote_pyclient` wheel | Independent HTTP client |
| `coyote_ingest` wheel | Submission tools and ingestion workers; core/client dependencies, with server composition for workers |

## Local development

Use [the uv workspace](uv-development.md) for editable installation. The equivalent
pip setup, from the repository root in a prepared development environment, is:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e core -e . -e clients/python -e 'services/ingest[worker]'
```

Python edits require process reload, not wheel builds. Metadata and dependency
changes require reinstalling or running `uv sync`.

## Core boundary

The core supplies clinical operations and contracts. It imports neither the API
nor MongoDB implementation. The adapter owns persistence. Frontend assets and
documentation remain separate deployment services. Report templates, styles and
fonts come from the pinned `smd-reports` dependency.

## Server entry point

Configure endpoints, logical database names, secrets, storage roots and the center
profile before starting the server. Pip installation does not provision MongoDB,
Redis, users or clinical configuration.

```bash
coyote4-api --host 127.0.0.1 --port 8001 --workers 1
# Equivalent:
uvicorn coyote_api.app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

The ingestion worker entry point is `coyote_ingest.celery_app:celery_app`.
Server maintenance uses `coyote_api.celery_app`. See
[deployment configuration](../deployment/configuration-reference.md) and
[center configuration](../deployment/center-configuration.md).

## Packaged resources

The core wheel contains canonical permission/role catalogs and the VEP grouping
policy. The server wheel contains documentation templates, logos, reference snapshots,
example center configuration and synthetic demo workflows. These resources live
in the API source tree and also ship in the server source distribution. The same
wheel contains the Mongo adapter's collection mappings and connection defaults.
The API and adapter retain separate folders and imports.

Credentials, deployment environment files, runtime outputs and patient data are
excluded. Operators supply a reviewed external center profile.

## Deployment

Ordinary Docker builds create core, server, Python client and ingestion wheels in an isolated build stage
and install them normally into the runtime image. API source directories do not
override the installed wheels. API and worker services use the same image.

The independent Python client supports the administrative commands shipped with
the image. API request handling and core operations do not import that client.

The retained-artifact release path verifies all four wheels against their
versions, SHA-256 digests and source provenance before installation.
See [release compatibility](compatibility.md#build-and-record-an-application-release).
