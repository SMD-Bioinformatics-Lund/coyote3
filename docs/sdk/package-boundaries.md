# Package boundaries and clinical records

The `Coyote3` distribution includes the core from `src/coyote3/` and the server
from root-level `api/`. A distribution boundary and an import boundary differ:
server modules ship in the wheel, but the core never imports them. `[api]` adds
FastAPI, MongoDB and other host dependencies. The remote Python client is built
separately from `clients/python/` and depends only on HTTPX and Pydantic.

| Location | Responsibility |
| --- | --- |
| `src/coyote3/application/` | Authorized operations, clinical workflows and repository/integration ports. |
| `src/coyote3/domain/` | Clinical rules, DNA/RNA logic, filtering, finding identity and validation. |
| `src/coyote3/contracts/` | Typed clinical and authored-resource contracts. `authoring/` describes editable inputs; it does not render browser widgets. |
| `src/coyote3/config/` | Software invariants, clinical defaults and explicit policy loading. |
| `src/coyote3/templates/reporting/` | Independently editable legacy/modern Jinja layouts, modality-specific components and embedded CSS. |
| `clients/python/src/coyote3_client/` | Authenticated HTTP client, resource objects and typed responses. |
| `api/app/` | Host composition, authentication adapters and runtime wiring. |
| `api/interfaces/http/v1/` | HTTP routes and transport behavior. |
| `api/contracts/` | HTTP envelopes, health/session responses, browser diagnostics, installation and trial-report transport models. |
| `api/services/` | Contact/about page composition and authorized installation operations. |
| `api/bootstrap/catalogs/` | RBAC, initial query publications, reference snapshots and synthetic installation fixtures. |
| `api/config/` | Deployment configuration, physical collection names, contact loading and the host logo. |
| `api/infra/` | MongoDB repositories, driver objects, storage, integrations and worker adapters. |
| `api/presentation/` | Web-host selection of the core's alternate report layout. |
| `demo_data/` | Synthetic connected demonstrations and ingest examples. |

## Clinical field names versus storage keys

SDK selections describe clinical records using paths such as
`INFO.selected_CSQ.SYMBOL`. Many paths currently match MongoDB document keys.
These names are part of the current clinical record contract; changing them
silently would alter query policies, filters and clinical behavior.

The SDK constructs database-neutral `Selection` objects. The MongoDB adapter
compiles them into MongoDB predicates in `api/infra/mongo/selection.py`.
`compile_selection(selection, field_names=...)` accepts explicit adapter-owned
field bindings, including nested array fields. A storage rename can therefore
be translated without rewriting the clinical selection. Literal values are
preserved; field bindings cannot move a nested condition outside its array.

This does not make existing dictionary-based clinical records independent of
their shape. A repository must also return records in the SDK's expected clinical
structure, translating stored records when necessary. Driver independence and
record-schema independence are different properties. A future storage adapter
must implement both selection translation and clinical record projection; it
does not require a second application SDK. SQL is not implemented.

## Bootstrap and center policy

Installed catalogs, demo installers, product-page metadata, contact loading and
logo assets remain outside the core namespace, in the API portion of the wheel.
Installation operations remain
authorized and audited host services. Clinical query defaults, vocabulary,
capability definitions and validation stay in the SDK because clinical operations
need them. A seed publication is installation data, rather than a runtime default.

The library accepts explicit vocabulary and filter metadata files. The API owns
environment discovery and additionally loads contact information for its web page.
See [getting started](getting-started.md) for the supported configuration boundary.

## Two Python interfaces

`from coyote3.application.operations import CoyoteApplication` gives a trusted
host local operations. The host must supply verified identity, current permissions,
repositories and integrations. Operation entry points enforce authorization.

`from coyote3_client import CoyoteClient` gives an external script resource objects
over HTTP. The server performs authentication, authorization and storage work.
For example, `sample.variants.tiered_variants()` invokes the supported API path.
Neither interface is part of FastAPI itself. See the [remote client guide](python-client.md).
