# Develop application operations and hosts

The SDK's supported local entry points are exported by
`coyote3.application.operations`. Use cases and domain rules implement those
operations; concrete runtime adapters belong to the consuming host. The API is
one such host, composed by `api/app/application_factory.py`. FastAPI dependencies
in `api/app/deps/application.py` obtain those composed application resources.

## Add an operation

1. Define its typed inputs, result and expected application errors. Reuse existing
   domain names and contracts. Specify null, ordering and pagination behavior.
2. Implement clinical/business rules in application or domain services. Define
   repository or integration protocols where required. Return application records
   rather than database driver objects or HTTP responses.
3. Add the operation to the appropriate resource under `application/operations/`.
   Invoke `ApplicationRuntime.execute` with its permission and sample scope
   requirements before service work. Do not accept actor identities or role lists
   in ordinary operation inputs.
4. Supply any new capability through the host-owned service factories. Concrete
   repositories remain in `api/infra/`; the library must never import `api`.
5. Add a thin HTTP handler if the operation needs HTTP access. Declare its route,
   permission dependencies and response contract, then delegate to the operation.
6. Cover successful and rejected calls, current permissions, sample ownership,
   validation and preserved clinical behavior. Update the supported exports,
   [operation guide](application-sdk.md) and generated reference.

## Compose a host

`ApplicationRuntime` receives authentication, current policy, sample/assay loaders
and an access-audit callback. `ApplicationServices` receives lazy implementation
factories. `CoyoteApplication(runtime, services)` exposes the resource objects.
Their full signatures are in the [reference](reference.md).

Release capture and validation also require a resource-integrity capability.
Supply `configure_resource_hasher(hasher)` from the supported operations exports
before executing those workflows, or use `using_resource_hasher(hasher)` for an
execution-scoped override. The callable receives an application record and returns
its deterministic persisted digest. The API/worker host supplies its canonical
BSON implementation from `api/infra/mongo/resource_integrity.py`; the library
does not import BSON or PyMongo. A host reading existing releases must preserve
the exact recorded digest format, including numeric, date and identity encoding.
Substituting ordinary JSON hashes would invalidate existing release integrity.

Authentication must reload current identity on every operation. Policy must
resolve current role grants and sample/assay access. An access audit failure must
prevent the operation from proceeding. Durable mutation audit, transactions and
outboxes remain owned by the existing services and repositories; an access event
does not establish that a mutation committed.

Worker hosts must use a restricted operation audience and service identity.
External scripts should normally use the HTTP client; a script with database
credentials already has the host's trust and is not sandboxed by Python resources.

Choose center configuration before importing vocabulary-dependent contracts, as
described in [getting started](getting-started.md). Runtime secrets, MongoDB
connections, Redis, SMTP and storage paths belong to host configuration. Typed
clinical values, software capabilities and configuration validation belong to
the library. Process-wide profile selection does not provide multiple independent
center profiles inside one Python process.

## Verify a change

Repository implementations translate selections and stored records at the
persistence boundary. Read [package boundaries](package-boundaries.md) before
changing clinical field paths or moving host code into the library.

```bash
.venv/bin/ruff check src api tests scripts
.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_application_sdk.py \
  tests/unit/test_library_configuration_boundary.py \
  tests/integration/test_api_architecture_boundaries.py
.venv/bin/python scripts/docs/export_sdk_reference.py
```

Cross-layer or clinical changes also require the relevant API, regression and
integration tests. Follow the [testing guide](../testing/README.md). Incompatible
supported Python changes require an SDK major release; internal implementation
changes do not automatically change the HTTP API major.
