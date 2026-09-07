# Contributing to Coyote3

Thank you for contributing to Coyote3.

Coyote3 is a clinical workflow platform used in molecular diagnostics. Contributions must prioritize correctness, traceability, security, and operational safety.

## Scope and ownership

Coyote3 is maintained by the Section for Molecular Diagnostics (SMD), Lund.

- External public contributions may be limited.
- Internal contributors should follow this guide for all code and documentation changes.

## Before you start

1. Open or review an issue describing the problem or change.
2. Confirm expected behavior, scope, and affected modules.
3. Verify whether the change affects interpretation logic, reporting, access control, or configuration behavior.

## Branch and commit guidelines

- Create a focused branch per change.
- Keep commits small and logically grouped.
- Use clear commit messages that describe intent and impact.
- Avoid mixing unrelated refactors with feature or bug-fix changes.

## Development standards

- Keep route handlers thin; move business logic into utility/handler layers.
- Preserve permission and sample-access checks for all relevant routes.
- Keep templates presentation-focused.
- Do not introduce breaking behavior in report lifecycle or historical traceability.
- Update documentation whenever behavior or workflow changes.

## Local validation

At minimum, validate:

1. The modified user flow works end-to-end.
2. Access control behavior is correct for authorized and unauthorized users.
3. Report preview/save/retrieval behavior still works if impacted.
4. No obvious regression in related pages.

Automated test coverage is evolving in this repository. Treat manual validation quality as a release-critical responsibility.

## Documentation requirements

For behavior changes, update relevant handbook chapters under `docs/handbook/`:

- user-facing chapters for workflow or UI changes
- developer-facing chapters for architecture, route, or data model changes

If documentation is not updated, the change is incomplete.

## Pull request expectations

A PR should include:

- clear problem statement
- implementation summary
- impacted routes/files/collections
- validation steps performed
- rollback considerations for risky changes

Use the repository PR template and link related issues.

## Change types with extra care

Apply heightened review discipline for:

- interpretation or classification logic
- report generation and persistence
- authentication, authorization, or permission changes
- admin schema/configuration changes
- database schema or migration behavior

## Security and sensitive data

- Never commit secrets, credentials, tokens, or private keys.
- Never commit patient-identifiable data or sensitive production datasets.
- Use sanitized or synthetic data for examples and debugging artifacts.
- Report security concerns through the process in `SECURITY.md`.

## Code of Conduct

By participating in this project, you agree to follow `CODE_OF_CONDUCT.md`.
