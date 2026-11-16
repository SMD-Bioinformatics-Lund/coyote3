# API host responsibilities

Routers validate transport inputs and delegate to core operations. The host
supplies current identities, assay/environment permissions, repositories, clocks,
integration clients and worker submission capabilities.

The API owns environment loading, web security, authentication, lifecycle,
request handling and presentation assets. The MongoDB package owns persistence
and physical collection contracts. Neither core nor adapter imports this host.

All entry points use the installed packages, including workers and operational
commands. Development uses editable installs; deployment installs built wheels.
The application does not add source directories to `sys.path` at runtime.

Report rendering remains delegated to `smd-reports` using the `coyote3` preset.
Framework-independent services preserve clinical wording, conditions, exact tier
matching, immutable snapshots, approval rules and finalization recovery.

Review HTTP contracts, scoped authorization and clinical regressions for changes.
Run package tests, the shared backend suite and affected frontend checks before
release. Package installation alone is not clinical deployment validation.
