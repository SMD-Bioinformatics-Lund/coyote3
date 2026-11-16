# API host responsibilities

Routers validate transport inputs and delegate to core operations. The host
supplies current identities, assay/environment permissions, repositories, clocks,
integration clients and worker submission capabilities.

The API owns environment loading, web security, authentication, lifecycle,
request handling and presentation assets. The MongoDB adapter owns persistence
and physical collection contracts. Neither core nor adapter imports this host.

The `coyote-server` distribution installs both the `coyote_api` and `coyote_mongo`
namespaces. They share the root project's version and dependencies, while keeping
separate source directories, documentation and tests. Distribution grouping does
not change the inward direction of imports or the core's repository interfaces.

All entry points use the installed packages, including workers and operational
commands. Development uses editable installs; deployment installs built wheels.
The application does not add source directories to `sys.path` at runtime.

Report rendering remains delegated to `smd-reports` using the `coyote3` preset.
Framework-independent services preserve clinical wording, conditions, exact tier
matching, immutable snapshots, approval rules and finalization recovery.

Review HTTP contracts, scoped authorization and clinical regressions for changes.
Run component tests, the shared backend suite and affected frontend checks before
release. Package installation alone is not clinical deployment validation.
