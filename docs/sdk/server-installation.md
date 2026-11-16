# Core, adapter, server and client installations

Packages are built locally; public-index publication is not required.

| Installation | Contents |
| --- | --- |
| `coyote_core` wheel | Clinical core and its own dependencies |
| `coyote_mongo` wheel | MongoDB adapter; requires the selected core |
| `coyote_api` wheel | API and worker host; requires the selected core and adapter |
| `coyote_pyclient` wheel | Independent HTTP client |

## Local development

Use [the uv workspace](uv-development.md) for editable installation. The equivalent
pip setup, from the repository root in a prepared development environment, is:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e core -e adapters/mongo -e api -e clients/python
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

Celery's entry point remains `coyote_api.celery_app`. See
[deployment configuration](../deployment/configuration-reference.md) and
[center configuration](../deployment/center-configuration.md).

## Packaged resources

The API wheel contains documentation templates, logos, installation catalogs,
example center configuration and synthetic demo workflows. These resources live
in its source tree and also ship in its source distribution. The adapter wheel
contains its collection mappings and connection defaults.

Credentials, deployment environment files, runtime outputs and patient data are
excluded. Operators supply a reviewed external center profile.

## Deployment

Ordinary Docker builds create three separate wheels in an isolated build stage
and install them normally into the runtime image. API source directories do not
override the installed wheels. API and worker services use the same image.

The retained-artifact release path verifies all three wheels against their
versions, SHA-256 digests and source provenance before installation.
See [release compatibility](compatibility.md#build-and-record-an-application-release).
