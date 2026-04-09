# ADR-0001: Resolve Authentication Provider From User Document

## Status

Accepted (2026-03-20)

## Context

Coyote3 runs across centers with different identity-provider setups. Static
allowlists in environment variables caused drift and operational overhead when
user populations changed.

## Decision

Authentication provider is resolved from persisted user data:

- `user.auth_type = coyote3` -> local password authentication
- `user.auth_type = ldap` -> LDAP authentication

No environment-based local-user allowlist is used for provider selection.

## Consequences

Positive:

- Per-user provider behavior is explicit, versionable, and auditable.
- Center onboarding is simpler (no local-user env sync required).
- UI behavior can rely on the same source of truth (`auth_type`).

Trade-offs:

- User data quality is now critical for auth routing.
- Migration paths must ensure legacy users get explicit/default `auth_type`.

## Follow-ups

- Add IdP adapters (for example SSO) using the same `auth_type` contract.
- Extend admin UX to make provider transitions safer and auditable.
