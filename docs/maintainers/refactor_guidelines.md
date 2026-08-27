# Engineering and Refactoring Standards

Use these standards when changing existing application behavior or structure.
They are intended to keep clinical workflows stable while allowing the codebase
to evolve.

## Preserve the Contract

Before changing implementation details, identify the contracts affected by the
change:

- HTTP request and response models;
- MongoDB document contracts and indexes;
- permissions and Casbin policy checks;
- audit events and user notifications;
- report content and saved report snapshots; and
- frontend states, including loading, empty, error, and permission-denied
  states.

Do not change a contract indirectly. A deliberate contract change must include
the corresponding schema, tests, documentation, and any required operational
procedure.

## Keep Responsibilities Separate

- HTTP routers validate transport input, apply dependencies, and return the
  application result.
- Application services coordinate use cases and authorization-aware workflow
  decisions.
- Domain code contains deterministic rules that do not depend on FastAPI or
  MongoDB.
- Repositories own collection access and index definitions.
- React pages compose user workflows; reusable presentation and interaction
  behavior belongs in components and hooks.

Avoid passing raw MongoDB collections outside the infrastructure composition
boundary. Avoid placing clinical decisions in routers or React components.

## Refactoring Procedure

1. **Establish the baseline.** Run the focused tests and record the current
   observable behavior.
2. **Define the boundary.** State which module or responsibility is moving and
   which contracts remain unchanged.
3. **Make a focused change.** Keep unrelated cleanup out of the same change
   unless it is required for correctness.
4. **Test each affected layer.** Add unit tests for extracted logic, API tests
   for route contracts, and frontend tests for user-visible behavior.
5. **Run repository checks.** Run formatting, linting, typing, contract, and
   documentation checks appropriate to the changed area.
6. **Review operational effects.** Check startup, indexes, background tasks,
   auditing, permissions, and deployment configuration when relevant.

## Error Handling

Catch exceptions only when the caller can add context, translate the error into
a stable application error, or perform required cleanup. Do not suppress an
unexpected exception or return a successful response for a failed write.

User-facing errors should explain the failed operation without exposing stack
traces, secrets, database internals, or protected sample data. Operational logs
should retain the request identifier and enough context for investigation.

## Data and Security Requirements

- Validate writes with the registered Pydantic contract.
- Apply the explicit permission for every protected operation.
- Preserve UTC timestamps in storage and convert them for display at the UI
  boundary.
- Keep collection names in the collection configuration, not domain code.
- Do not add sample identifiers, patient information, credentials, or tokens to
  fixtures, documentation, or commits.
- Do not weaken an authorization check to simplify a test or integration.

## Completion Criteria

A refactor is complete when the behavior is covered at the appropriate layers,
the relevant documentation matches the implementation, generated contracts are
current, and the focused quality suite passes. Broader test suites are required
when the change affects shared infrastructure or cross-domain behavior.
