# ADR-0001: Resolve Authentication Provider From User Document

## Status

Accepted (2026-03-20)

## Context

Coyote3 runs across centers with different identity-provider setups. Static
allowlists in environment variables caused drift and operational overhead when
user populations changed.

## Decision

Authentication provider is resolved from persisted user data:

- `user.auth_type = ["local"]` -> local password authentication by username
- `user.auth_type = ["ldap"]` -> LDAP authentication by email
- `user.auth_type = ["local", "ldap"]` -> both login paths are allowed

Human center accounts default to `["ldap"]`. They may be explicitly configured
as `["local", "ldap"]` when both center LDAP login and Coyote3-managed local
password login are required. Coyote service accounts (`coyote3.admin` and
`coyote3.*`) default to `["local"]`.

No environment-based local-user allowlist is used for provider selection.

## Consequences

Positive:

- Per-user provider behavior is explicit, versionable, and auditable.
- Center onboarding is simpler (no local-user env sync required).
- UI behavior can rely on the same source of truth (`auth_type`) and render
  one badge per configured provider.

Trade-offs:

- User data quality is now critical for auth routing.
- Migration paths must ensure historical users get explicit/default `auth_type`.

## Follow-ups

- Add IdP adapters (for example SSO) using the same `auth_type` contract.
- Extend admin UX to make provider transitions safer and auditable.
