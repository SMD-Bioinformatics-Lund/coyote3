# Use clinical operations in a host

Use the exports in `coyote.application.operations` as the supported in-process
interface. A host supplies two kinds of capabilities:

- `ApplicationRuntime`: current authentication, permission checks, scope checks
  and access auditing.
- `ApplicationServices`: factories for the services and integrations used by
  operations.

After constructing those capabilities, bind them to the application:

```python
from coyote.application.operations import (
    ApplicationRuntime,
    ApplicationServices,
    CoyoteApplication,
)

def bind_application(
    runtime: ApplicationRuntime,
    services: ApplicationServices,
) -> CoyoteApplication:
    return CoyoteApplication(runtime=runtime, services=services)
```

This binds existing capabilities; it does not create credentials, grant access
or provision storage. Operations revalidate current identity and policy rather
than treating a retained application object as a permanent authorization grant.

The operation surface covers samples, findings, reporting, rule authoring,
configuration governance, ingestion and administration. Services enforce the
clinical rules and workflow transitions. A host should delegate to these
operations instead of reproducing their logic in route handlers.

Results use typed records and operation contracts. Application failures use
`AppError`; the host translates them into its transport's response format.
Database driver results and executable MongoDB predicates stay in adapters.

Select the center profile before importing vocabulary-dependent operations.
See [configuration](configuration.md), [reference](reference.md) and
[architecture](architecture.md).
