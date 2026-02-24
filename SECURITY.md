# Security Policy

## Supported versions

Security fixes are prioritized for actively maintained versions used in production diagnostics workflows.

As a practical policy, report issues against the currently deployed production version and the latest development branch.

## Reporting a vulnerability

Do not report security vulnerabilities in public issues.

Report vulnerabilities privately to project maintainers through internal security/operations channels used by the Section for Molecular Diagnostics (SMD), Lund.

If you are unsure of the correct channel, contact the maintainers first and request secure reporting instructions.

## What to include in a report

Provide enough detail for reproducibility and triage:

- vulnerability type and impact
- affected component or route
- affected version/branch
- reproduction steps
- proof-of-concept details (sanitized)
- suggested mitigation, if known

Do not include secrets, credentials, or sensitive patient data in reports.

## Response and triage process

Maintainers will:

1. Acknowledge receipt.
2. Assess severity and scope.
3. Validate and reproduce the issue.
4. Prepare and review a fix.
5. Coordinate deployment timing based on operational risk.

## Disclosure policy

Security issues are handled under responsible disclosure.

- Public disclosure should happen only after a fix is available or a mitigation is in place.
- Timing and disclosure detail are determined by maintainers based on patient-safety and operational considerations.

## Security best practices for contributors

- Never commit secrets, tokens, or private keys.
- Never commit sensitive production data.
- Preserve authentication and authorization checks in route changes.
- Treat report-generation and history endpoints as high-risk surfaces.
- Document any security-relevant behavior changes in PRs.
