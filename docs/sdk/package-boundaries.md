# Package boundaries

The core imports as `coyote`; the application remains Coyote4. Each Python
distribution has its own project metadata, tests, documentation and GPLv3 license.

| Distribution | Source | Permitted dependencies within this repository |
| --- | --- | --- |
| `coyote-core` | `core/src/coyote/` | None |
| `coyote-mongo` | `adapters/mongo/src/coyote_mongo/` | Core |
| `coyote-api` | `api/src/coyote_api/` | Core and MongoDB adapter |
| `coyote-pyclient` | `clients/python/src/coyote_pyclient/` | None; communicates over HTTP |

## Shared core and request flow

![Package dependencies and runtime request flow](../assets/diagrams/package-dependencies.svg)

[Open the full-size SVG](../assets/diagrams/package-dependencies.svg).

Core is the shared foundation for the API and MongoDB adapter. It owns clinical
operations, typed contracts and repository interfaces. The adapter implements
those interfaces; the API constructs the repositories and supplies them to core
services. Both packages depend on core, and the API also depends on the adapter.
Core does not import either implementation.

For a variant-review request:

1. The React frontend or external Python client sends an HTTP request to the API.
2. The API authenticates the caller, enforces request access and invokes a core operation.
3. Core applies the clinical workflow and calls its supplied repository interfaces.
4. The Mongo implementation translates repository operations into database queries.
5. Results return through the interfaces, core operation and API to the caller.

The top diagram shows code dependencies; the lower diagram shows runtime calls.
Calling an injected repository does not make core import MongoDB. API, core and
adapter run inside the same backend process; packaging does not create additional
network services. Workers also invoke core operations through host composition.

The Python HTTP client is intended for external integrations. The frontend uses
its own TypeScript HTTP client, and backend services invoke core directly. Neither
uses the Python client at runtime. Application integration tests use it to verify
the HTTP boundary. Its separate repository and PyPI release are tracked in
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
composition, installation resources and workers. Routes delegate clinical behavior
to core operations. The HTTP client owns independent wire models and never
imports the core or adapter.

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
