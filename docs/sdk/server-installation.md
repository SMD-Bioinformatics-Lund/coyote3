# Core, server and client installations

| Installation | Distribution contents and dependencies |
| --- | --- |
| `pip install coyote3` | Core dependencies. The wheel also contains dormant API modules; importing the core does not import FastAPI, MongoDB drivers or server configuration. |
| `pip install "coyote3[api]"` | The same wheel plus FastAPI, MongoDB, Celery, Redis and other declared server dependencies. |
| `pip install "coyote3[all]"` | All declared API, development, testing, documentation and load-tool extras. |
| `pip install coyote3-client` | Independent HTTPX/Pydantic client, with no dependency on the core or API distribution. |

For a local checkout use `pip install -e ".[api]"` and, separately,
`pip install -e clients/python`. Normal production builds use wheels. Publishing
to a public index is a separate release operation; local wheels work without it.

The center installer builds the application wheel inside Docker automatically.
Its normal Compose configuration does not require a prebuilt SDK artifact directory.
Release CI can instead select the verified-wheel build described in
[release compatibility](compatibility.md#build-and-record-an-application-release).

## Core boundary

`src/coyote3/` contains reusable domain logic, application workflows, authorization,
typed clinical contracts, configuration validation and report rendering/templates.
It imports neither `api` nor `coyote3_client`. Hosts supply authenticated identities,
current policy, repositories and integration capabilities. The core never supplies
database credentials or grants permissions merely because it is installed.

Root-level `api/` contains FastAPI routes, authentication adapters, MongoDB
repositories, concrete integrations, Celery wiring, host configuration and
installation operations. Its existing organization is retained. Package extras
control dependencies; they cannot select different files from the same wheel.

`clients/python/` builds the separate `coyote3-client` wheel. Both sync and async
clients communicate through HTTP and share client-owned wire models. OpenAPI
contract tests check their actual endpoints. No client applies clinical rules or
enforces server permissions. No TypeScript package is added: the frontend already
has its own typed HTTP/query abstractions.

## Server entry point

Configure database endpoints, application/identity/knowledgebase/BAM database
names, secrets, storage roots and an external center profile before starting the
server. The installed application uses the same settings as Docker/Compose.
See [deployment configuration](../deployment/configuration-reference.md) and
[center configuration](../deployment/center-configuration.md).

```bash
coyote3-api --host 127.0.0.1 --port 8001 --workers 1
# Equivalent ASGI entry point:
uvicorn api.app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

The Celery entry point remains `api.celery_app`. MongoDB, Redis and worker services
are external runtime dependencies; pip installation does not start or provision
them. Frontend assets and the documentation site remain separate deployment
services. Existing Compose and container entry points are unchanged.

## Packaged resources

Setuptools discovers `coyote3` from `src/` and `api` from the repository root.
`build_support.ServerBuildPy` copies authoritative release metadata, example center
files and connected demo resources into the API portion of a normal wheel.
Source inputs remain in their existing locations. `MANIFEST.in` includes them in
source distributions, so building from an sdist retains the same resources.

API documentation templates, installation catalogs and logo assets ship as API
package data. Report templates/CSS ship under `coyote3/templates/reporting/`.
Environment files, credentials, patient data and runtime output are not packaged.
Operators should supply their reviewed external center profile; bundled examples
are not a substitute for center configuration.

Installation tests build real wheels, install them into separate targets, disable
editable lookup, and run outside the checkout. They verify core/client import
isolation, both report layouts, API import, ASGI selection and required resources.

The Coyote3 wheel has one immutable distribution version, covering both core and
bundled server files. A server-only code change still needs a new Coyote3 wheel
version when published. The complete deployment release and independent client
version are tracked separately; see [versions](compatibility.md).
