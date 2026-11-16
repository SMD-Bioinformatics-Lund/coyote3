# Package boundaries

The core imports as `coyote`; the application remains Coyote4. Each Python
distribution has its own project metadata and GPLv3 license. API and Mongo
components retain separate source, tests, coverage and guides inside one server distribution.

| Distribution | Source | Permitted dependencies within this repository |
| --- | --- | --- |
| `coyote-core` | `core/src/coyote/` | None |
| `coyote-server` | `api/src/coyote_api/`, `adapters/mongo/src/coyote_mongo/` | Core; API composes the Mongo component |
| `coyote-pyclient` | `clients/python/src/coyote_pyclient/` | None; communicates over HTTP |
| `coyote-ingest` | `services/ingest/src/coyote_ingest/` | Core and Python client; the worker extra uses server composition |

## Shared core and request flow

![Package dependencies and runtime request flow](../assets/diagrams/package-dependencies.svg)

[Open the full-size SVG](../assets/diagrams/package-dependencies.svg).

Core is the shared foundation for the API and MongoDB adapter. It owns clinical
operations, typed contracts and repository interfaces. The adapter implements
those interfaces; the API constructs the repositories and supplies them to core
services. Both components depend on core, and the API also depends on the adapter.
Core does not import either implementation. The ingestion service also uses core;
its workers obtain database and authentication wiring from the server. The server
publishes named ingestion tasks without importing the ingestion service.

For a variant-review request:

1. The React frontend or external Python client sends an HTTP request to the API.
2. The API authenticates the caller, enforces request access and invokes a core operation.
3. Core applies the clinical workflow and calls its supplied repository interfaces.
4. The Mongo implementation translates repository operations into database queries.
5. Results return through the interfaces, core operation and API to the caller.

The diagram separates code dependencies, runtime calls and ingestion dependencies.
Calling an injected repository does not make core import MongoDB. API, core and
adapter run inside the same backend process; packaging does not create additional
network services. Workers also invoke core operations through host composition.

The Python HTTP client is intended for external integrations. The frontend uses
its own TypeScript HTTP client, and backend services invoke core directly. Neither
uses the Python client for application requests. Administrative HTTP commands
shipped with the server image and application integration tests use it to verify
and operate the HTTP boundary. Its separate repository and PyPI release are tracked in
[future work](../project/future-work.md#independent-python-http-client-repository-and-pypi-release).

## Package responsibilities

The core contains domain decisions, typed contracts and use cases. Hosts supply
identities, current permission policy, repositories, clocks and integration ports.
The core does not import API modules, database drivers, task queues or HTTP clients.

The adapter owns physical collections, provider identities, MongoDB operators,
indexes and transactions. It exposes portable results through core contracts.
API settings reuse its connection defaults rather than defining a second copy.
Host callbacks provide optional operation metrics; importing the adapter does not
import the API or start connections.

The API owns web authentication, environment loading, request handling,
composition, reference installation and maintenance workers. Routes delegate
clinical behavior to core operations. The HTTP client owns independent wire models
and never imports the core or adapter.

The ingestion package owns pipeline submission commands and Celery ingestion tasks.
Reusable parsing, validation, job execution and manifest-watching workflows belong
to core. HTTP uploads, process entry points and task-queue integration stay outside
core. See the [ingestion service guide](../../services/ingest/docs/README.md).

Core owns the canonical permission and role catalogs and Coyote's VEP interpretation
policy. The server packages HGNC/VEP reference snapshots and installs them explicitly
through the Mongo adapter. Installed accounts, grants and reference selections remain
deployment state; importing packages or redeploying does not reset them.

The API's `config/backend.py` assembles and validates package-specific deployment
inputs. The Mongo adapter accepts `MongoSettings` and explicit logger/cache ports,
while public core operations accept `PublicSettings` availability flags. Center
policy uses the existing explicit `CenterConfiguration`. Independent packages do
not load environment files or discover deployment settings from process variables.
Installing from a wheel or using an editable checkout has the same configuration
contract. Libraries sharing a process are not isolated from its environment.

A future database adapter must implement repository operations and preserve
selection, identity, missing/null, transaction and snapshot semantics. Database
independence is a contract to satisfy, not a promise that changing a connection
string supports another engine.

Architecture tests reject reverse dependencies. Installed-wheel tests execute
outside the checkout with editable lookup removed, checking imports and assets.
See [uv development](uv-development.md) for package tests and builds.
