# ADR-0002: Local Password Lifecycle With Email Fallback

## Status

Accepted (2026-03-20)

## Context

Centers need a consistent lifecycle for local users:

- admin invite for first-time setup
- self-service password reset
- authenticated password change

SMTP availability differs between environments and cannot be assumed.

## Decision

For local users (`auth_type=coyote3`), Coyote3 issues one-time password action
tokens (invite/reset) and attempts email delivery through configured SMTP.

When SMTP is unavailable or sending fails:

- flows do not hard-fail
- API/UI return warning metadata and manual `setup_url`
- admin workflows remain operational

## Consequences

Positive:

- User onboarding/reset remains available during mail outages.
- Runtime behavior is predictable across center-specific mail infrastructure.
- Security posture is preserved via one-time, expiring tokens.

Trade-offs:

- Manual URL handoff is operationally less convenient than successful email.
- Monitoring/alerting is needed to detect degraded mail delivery quickly.

## Follow-ups

- Add center-level mail health dashboard and alert rules.
- Add LDAP/IdP-native password change UX where provider policy allows.
