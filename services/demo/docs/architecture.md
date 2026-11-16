# Architecture

The base package depends on `coyote-core`. It owns synthetic configuration,
manifests, raw examples, catalog compilation and installation coordination.
The optional server integration supplies persistence repositories, current
session permissions, audit context and the ordinary ingestion implementation.

The `coyote.api.routers` entry point returns no routes when the package is
disabled. When enabled, target validation precedes route registration. The
`coyote.runtime.validators` entry point checks selected demonstration settings
before a host opens database connections. Installation also checks actual database
handles and authenticated privileges before writes.

Clinical schemas, parsing, finding identity and report rules remain in core.
Mongo transaction and reviewed-record protections remain in the server adapter.
Demo data is synthetic training material; changing it must not silently update
frozen clinical regression expectations in another package.
