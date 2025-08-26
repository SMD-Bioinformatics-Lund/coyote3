# Security & Threat Model

**Assets**: PHI/PII in samples and findings; credentials; audit logs.  
**Actors**: authenticated users by role; admins; service accounts.

**Controls**
- AuthN: LDAP or local; sessions via Flask‑Login.
- AuthZ: RBAC + per‑sample assay checks.
- CSRF: enabled.
- Logging: centralized + audit trail (`@log_action`).
- Secrets: `COYOTE3_FERNET_KEY` for encryption; keep keys outside the DB.

**Risks & Mitigations**
- Broken access control → strict decorators and server‑side checks.
- Sensitive logs → avoid writing raw PHI; mask identifiers where possible.
- Backup leaks → encrypt dumps at rest; restrict access.
