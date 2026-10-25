# Coyote3 SDK

The installable `Coyote3` distribution contains the core application library and
root-level API modules. Core imports are independent of FastAPI; `[api]` installs
server dependencies. The remote HTTP client is a separate `coyote3-client`
distribution maintained in `clients/python/`.

| Task | Guide |
| --- | --- |
| Install the library or choose local operations versus HTTP access | [Getting started](getting-started.md) |
| Understand package ownership, clinical record fields and storage boundaries | [Package boundaries](package-boundaries.md) |
| Invoke local operations and understand permissions, scopes and results | [Application operations](application-sdk.md) |
| Understand enforced permissions and trusted-host responsibilities | [SDK permissions](permissions.md) |
| Authenticate to a running installation from Python | [Remote Python client](python-client.md) |
| Add operations, implement repository ports or compose a trusted host | [SDK development](extending.md) |
| Look up public Python signatures and their documented behavior | [Python reference](reference.md) |
| Release the library or select a compatible application/SDK combination | [Versions and compatibility](compatibility.md) |

Clinical users follow the [user guide](../user-guide/README.md). Administrators
follow the [administration guide](../administration/README.md). Operators select
external [center configuration](../deployment/center-configuration.md).

SDK documentation is maintained here alongside its code and tests. It is published
in the shared documentation site; it is not duplicated inside `src/coyote3/` or
included as runtime package data.
