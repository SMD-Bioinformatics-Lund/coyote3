# Package boundaries

The core imports as `coyote`; the application remains Coyote4. Each Python
distribution has its own project metadata and GPLv3 license. API and Mongo
components retain separate source, tests, coverage and guides inside one server distribution.

| Distribution | Source | Dependencies between Coyote components |
| --- | --- | --- |
| `coyote-contracts` | `src/coyote_contracts/` in its external repository | None; Pydantic and PyYAML only |
| `coyote-core` | `core/src/coyote/` | Contracts; no API or database implementation |
| `coyote-server` | `api/src/coyote_api/`, `adapters/mongo/src/coyote_mongo/` | Core; API composes the Mongo component |
| `coyote-pyclient` | `src/coyote_pyclient/` in the external client repository | None; Pydantic and HTTPX for its independent HTTP interface |
| `coyote-relay` | `coyote_relay` in the external Relay repository | Contracts and HTTPX; clinical validation adds core, API/worker integrations add server |
| `coyote-atlas` | `services/atlas/src/coyote_atlas/` | Core and HTTPX; optional API integration uses the server |
| `coyote-demo` | `services/demo/src/coyote_demo/` | Core; optional API integration uses the server, and worker integration uses Relay |

## Shared core and request flow

![Package dependencies and runtime request flow](../assets/diagrams/package-dependencies.svg)

[Open the full-size SVG](../assets/diagrams/package-dependencies.svg).

Core is the shared foundation for the API and MongoDB adapter. It owns clinical
operations, typed contracts and repository interfaces. The adapter implements
those interfaces; the API constructs the repositories and supplies them to core
services. Both components depend on core, and the API also depends on the adapter.
Core does not import either implementation. Its portable sample input models and
permitted resource metadata come from `coyote-contracts`, which has no dependency
on core. Relay's submission commands use contracts directly; its optional clinical
validation and workers use core. Workers obtain database and authentication wiring
from the server. The server
publishes named ingestion tasks without importing worker code. Installed Relay
API routes are discovered through the `coyote.api.routers` entry-point group.
The server distribution has no required dependency on Relay.

For a variant-review request:

1. The React frontend or external Python client sends an HTTP request to the API.
2. The API authenticates the caller, enforces request access and invokes a core operation.
3. Core applies the clinical workflow and calls its supplied repository interfaces.
4. The Mongo implementation translates repository operations into database queries.
5. Results return through the interfaces, core operation and API to the caller.

The diagram separates code dependencies, runtime calls and optional package responsibilities.
Calling an injected repository does not make core import MongoDB. API, core and
adapter run inside the same backend process; packaging does not create additional
network services. Workers also invoke core operations through host composition.

The Python HTTP client is intended for external integrations. The frontend uses
its own TypeScript HTTP client, and backend services invoke core directly. Neither
uses or installs the Python client for application requests. Server administration
and Relay use their own HTTP transport. Its repository is independent; PyPI publication remains tracked in
[future work](../project/future-work.md#independent-python-http-client-repository-and-pypi-release).

## Package responsibilities

Contracts owns structural manifests, YAML normalization, permitted metadata and
bounded retrieval request models. It reads no environment settings and has no
database or clinical dependencies. Core's `SamplesDoc` extends its `SampleManifest`
with center vocabulary, sequencing policy, clinical filters and persistence fields.
A successful structural check is not clinical acceptance.

The core contains domain decisions, clinical contracts and use cases. Hosts supply
identities, current permission policy, repositories, clocks and integration ports.
The core does not import API modules, database drivers, task queues or HTTP clients.

The adapter owns physical collections, provider identities, MongoDB operators,
indexes and transactions. It exposes portable results through core contracts.
API settings reuse its connection defaults rather than defining a second copy.
Host callbacks provide optional operation metrics; importing the adapter does not
import the API or start connections.

The API owns web authentication, environment loading, request handling,
composition, installation orchestration and maintenance workers. Routes delegate
clinical behavior to core operations. The HTTP client owns its independent wire
models and never imports contracts, core or the adapter.

Relay owns pipeline submission commands, ingestion HTTP routes and Celery tasks.
YAML and structural validation belong to contracts. Clinical parsing, validation,
job execution and manifest-watching workflows belong to core. HTTP uploads, process
entry points and task-queue integration stay outside
core. See the [ingestion service guide](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/README.md).

Core owns the canonical permission and role catalogs and Coyote's VEP interpretation
policy. Atlas owns HGNC/VEP snapshots, provenance, validation and reference
publication workflows. The server discovers its installed reference provider and
supplies Mongo persistence. Installed accounts, grants and reference selections
remain deployment state; importing packages or redeploying does not reset them.

Demo owns synthetic resources and demonstration installation. Its API extension
registers only when explicitly enabled with isolated demo databases, restricted
credentials and disabled external integrations. Installation in an ordinary
workspace does not activate its routes. The runtime validator receives only its
declared configuration keys and checks the target before database initialization.
See [isolated demo deployment](../deployment/demo-installation.md).

The API's `config/backend.py` assembles and validates package-specific deployment
inputs. The Mongo adapter accepts `MongoSettings` and explicit logger/cache ports,
while public core operations accept `PublicSettings` availability flags. Center
policy uses the existing explicit `CenterConfiguration`. Core and the database
adapter do not discover deployment settings from process variables. Relay's CLI
accepts its own `COYOTE_RELAY_*` connection settings, with command-line values
taking precedence. Its optional API and worker hosts reuse server configuration.
Installing from a wheel or using an editable checkout has the same configuration
contract. Libraries sharing a process are not isolated from its environment.

A future database adapter must implement repository operations and preserve
selection, identity, missing/null, transaction and snapshot semantics. Database
independence is a contract to satisfy, not a promise that changing a connection
string supports another engine.

Architecture tests reject reverse dependencies. Installed-wheel tests execute
outside the checkout with editable lookup removed, checking imports and assets.
See [uv development](uv-development.md) for package tests and builds.

Each component keeps its own tests, synthetic helpers, smoke checks and coverage
gate. Root tests cover composition and repository workflows. Shared test utilities
belong in a development-only testkit only when multiple packages need the same
stable helper; they must not make package tests depend on another package's test
tree. There is no deployed testing service. Demonstration data can support
acceptance runs, while frozen regression fixtures remain owned by their tests.

Relay can be built and installed from its independent repository without a source
checkout at runtime. Release validation and publication are tracked
in [future work](../project/future-work.md#independent-coyote-relay-repository-and-release).
