# Permissions and trusted SDK hosts

Supported application operations enforce authorization inside the SDK through
`ApplicationRuntime.execute`. Calling the operations directly does not bypass the
checks performed by HTTP workflows.

For every operation the runtime reloads authenticated identity, checks the
credential's operation audience, enforces required password changes, evaluates
current permission grants and checks sample/assay scope where applicable. Some
operations require additional permissions based on the loaded resource, such as
production publication. Authorization failures prevent service execution.

Permission declarations are explicit. A catalog permission tuple requires every
listed grant. `None` selects an authenticated operation whose implementation owns
recipient/account scoping; an empty tuple is rejected as a composition error.
Anonymous published-catalog reads use the separate `PublicApplication` capability.
Pipeline and worker identities have restricted operation audiences.

Access auditing runs before service work. Audit failure prevents execution.
Mutation audit, transaction boundaries and durable outboxes remain in their
existing services and repositories. An allowed access event is not evidence that
a mutation committed.

## Host responsibilities

The host supplies verified authentication, current permission policy, sample/assay
loaders and accepted audit persistence. The API host revalidates its server-side
session and current account for each operation; callers do not supply their own
roles or actor through ordinary operation inputs.

A custom host must provide equally trusted capabilities. The SDK does not sandbox
arbitrary Python or protect a database from someone who already holds database
credentials. Internal services and domain helpers are implementation interfaces;
external integrations normally use the remote client and the server's controls.

The remote Python client does not implement authoritative permission enforcement.
Its requests go through the API and application-operation checks. UI visibility
and client-side errors are not access-control decisions.

## Relevant checks

`tests/unit/test_application_sdk.py` covers revoked sessions/grants, changed sample
scope, required password replacement, credential audiences and audit failures.
HTTP authorization matrices and ingestion credential tests cover the corresponding
transport and machine entry points. See the [security architecture](../architecture/security-model.md)
and [application-operation guide](application-sdk.md).
