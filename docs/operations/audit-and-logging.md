# Audit Events And JSON Logging

Coyote3 separates operational diagnostics from durable security and workflow audit events.

Runtime logs are JSON Lines written to stdout and, when enabled, rotating files under `LOGS`.
Every API request binds a request context so log records can include `request_id`, client IP,
method, and path. The API returns the correlation id in the `X-Request-ID` response header.

Durable audit events are append-only MongoDB documents in `AUDIT_EVENTS_COLLECTION`
(`audit_events` by default). Events include:

- `occurred_at` and `expires_at`
- `severity`, `category`, `event_type`, and `outcome`
- actor username/fullname/roles/provider
- resource type/id/name
- request source metadata
- bounded, redacted metadata

Metadata keys resembling passwords, secrets, tokens, cookies, authorization headers, sequences,
report bodies, or file contents are redacted before storage.

API sessions are opaque random tokens. Only a SHA-256 hash is stored in `API_SESSIONS_COLLECTION`
(`api_sessions` by default), together with `user_id`, `csrf_token`, `created_at`,
`last_seen_at`, and `expires_at`. Disabled or missing users are rejected during session lookup.

Indexes are created at runtime for session expiry and audit retention/filtering:

- `ttl_api_session_expiry`
- `ttl_audit_expiry`
- audit indexes for time, severity, category, event type, actor, and tags

Relevant settings:

```text
API_SESSION_COOKIE_NAME
API_SESSION_COOKIE_SAMESITE
API_SESSION_TTL_SECONDS
API_SESSIONS_COLLECTION
AUDIT_EVENTS_COLLECTION
AUDIT_RETENTION_DAYS
LOG_SERVICE_NAME
LOG_FILE_ENABLED
LOG_RETENTION_DAYS
LOG_LEVEL
```

