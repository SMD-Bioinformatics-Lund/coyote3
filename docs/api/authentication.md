# API Authentication

Coyote3 uses one session model for browser users and API-only clients. A
successful login creates an opaque API session token in MongoDB. The token is
returned to the caller as an HTTP cookie and can also be sent as a bearer token
by scripts, notebooks, and command-line clients.

## OpenAPI Authorization Options

Swagger UI shows two authorization schemes:

| Scheme | Transport | Typical use |
| --- | --- | --- |
| `ApiSessionCookie` | Cookie named by `API_SESSION_COOKIE_NAME` | Browser sessions and Swagger used from the same browser session. |
| `BearerAuth` | `Authorization: Bearer <token>` | API-only clients that capture the session token from login. |

The cookie name is environment-specific. In the development environment it is
commonly `coyote3_dev_api_session`. Production and test deployments can use
different names through `API_SESSION_COOKIE_NAME`.

> **Info: Same token, two transports**
>
>
> `ApiSessionCookie` and `BearerAuth` are not two separate credential systems.
> Both carry the same opaque session token. The API first checks the bearer
> header and then falls back to the configured session cookie.
>

## Getting A Session For API-Only Use

Create a session by calling the login endpoint through the same public mount
prefix used by the application.

Set the mounted public origin, then read the enabled providers. The response
contains one or both of `local` and `ldap`, as configured in
`api/config/center/clinical_vocabulary.toml`.

```bash
BASE_URL="https://localhost/coyote3_dev"
curl -sS "${BASE_URL}/api/v1/auth/providers"
```

Use `local` with a local username and password. Use `ldap` with the user's
email address and directory password. The provider is explicit so an API client
does not rely on UI behavior or heuristic identifier detection.

```bash
curl -i -sS -X POST "${BASE_URL}/api/v1/auth/sessions" \
  -H "Content-Type: application/json" \
  --data '{
    "username": "admin.coyote3",
    "password": "REPLACE_WITH_PASSWORD",
    "provider": "local"
  }'
```

The response body contains the authenticated user payload. The session key is
in the `Set-Cookie` response header:

```http
Set-Cookie: coyote3_dev_api_session=<opaque-session-token>; HttpOnly; SameSite=lax; ...
```

For LDAP users, submit the email address in the `username` field. For local
users, submit the local username. The `provider` value must be enabled by the
center's vocabulary configuration.

> **Warning: Handle session tokens as secrets**
>
>
> The session token gives the holder the same permissions as the logged-in
> user until the token expires or is deleted. Do not store it in source code,
> shell history, notebooks, tickets, screenshots, or documentation.
>

## Calling The API With A Cookie Jar

Cookie authentication requires the login response's `csrf_token` in the
`X-CSRF-Token` header for mutations, including logout. Protect cookie files
with restrictive permissions and remove them when the script finishes.

```bash
BASE_URL="https://localhost/coyote3_dev"
COOKIE_JAR=".coyote3-api.cookies"
umask 077

CSRF_TOKEN="$(curl -fsS -c "${COOKIE_JAR}" -X POST "${BASE_URL}/api/v1/auth/sessions" \
  -H "Content-Type: application/json" \
  --data '{
    "username": "admin.coyote3",
    "password": "REPLACE_WITH_PASSWORD",
    "provider": "local"
  }' | python3 -c 'import json, sys; print(json.load(sys.stdin)["csrf_token"])')"

curl -sS -b "${COOKIE_JAR}" "${BASE_URL}/api/v1/auth/whoami"
```

Delete the current session when the script is finished:

```bash
curl -fsS -b "${COOKIE_JAR}" -X DELETE \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  "${BASE_URL}/api/v1/auth/sessions/current"
rm -f "${COOKIE_JAR}"
unset CSRF_TOKEN
```

## Calling The API With BearerAuth

API-only clients may extract the session token from `Set-Cookie` and send it as
a bearer token.

```bash
BASE_URL="https://localhost/coyote3_dev"
COOKIE_NAME="coyote3_dev_api_session"

SESSION_TOKEN="$(
  curl -sS -i -X POST "${BASE_URL}/api/v1/auth/sessions" \
    -H "Content-Type: application/json" \
    --data '{
      "username": "admin.coyote3",
      "password": "REPLACE_WITH_PASSWORD",
      "provider": "local"
    }' |
  awk -v cookie="${COOKIE_NAME}" '
    BEGIN { IGNORECASE = 1 }
    /^set-cookie:/ {
      marker = cookie "="
      start = index($0, marker)
      if (start > 0) {
        value = substr($0, start + length(marker))
        split(value, parts, ";")
        print parts[1]
      }
    }
  '
)"

curl -sS "${BASE_URL}/api/v1/auth/whoami" \
  -H "Authorization: Bearer ${SESSION_TOKEN}"
```

Swagger's `BearerAuth` field expects the raw token value. Do not include the
literal `Bearer ` prefix in the Swagger dialog; Swagger adds that prefix to the
request.

## Using Swagger UI

Open Swagger UI through the mounted application path:

```text
https://localhost/coyote3_dev/api/v1/docs
```

Recommended workflow:

1. Sign in through the Coyote3 UI in the same browser.
2. Open Swagger UI under the same host and `SCRIPT_NAME`.
3. Run protected requests. The browser sends the HTTP-only session cookie with
   same-origin API requests.

You can also call `POST /api/v1/auth/sessions` from Swagger itself. A successful
response sets the session cookie for that browser origin.

> **Caution: Manual cookie authorization**
>
>
> Browsers do not allow JavaScript clients to set arbitrary `Cookie` headers.
> If the Swagger authorization dialog displays `ApiSessionCookie`, normal use
> is still to create a session first and let the browser carry the cookie.
> Use `BearerAuth` for manually pasted API-only tokens.
>

## Session Validation And Logout

Password reset tokens are consumed atomically with the password update. A token
can change the password only once. Changing a password invalidates sessions
created against an earlier credential state; sign in again after the change.
Sessions are bound to a fingerprint of the stored password hash, not a timestamp.
The fingerprint is internal session metadata and is excluded from user responses.
Sessions without this binding must sign in again when the protection is deployed.
An account marked `must_change_password` can read its identity/session, change
its password, and log out, but cannot access protected clinical or administrative
operations, including when it has the superuser role.

Login and logout clear browser query caches and in-memory notifications. Table
search text and notification content are not persisted in browser storage.
Durable approval notifications remain in the authenticated server inbox.

Use these endpoints to validate or remove the active session:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/v1/auth/providers` | `GET` | Returns the center-enabled login providers for public clients. |
| `/api/v1/auth/whoami` | `GET` | Returns username, roles, active role, access level, and effective permissions. |
| `/api/v1/auth/session` | `GET` | Returns the complete serialized session user payload used by the UI. |
| `/api/v1/auth/sessions/current` | `DELETE` | Deletes the current bearer or cookie-backed API session. |

## Prefix-Aware URLs

When `SCRIPT_NAME=/coyote3_dev`, all user-facing API documentation and API calls
go through that prefix:

```text
https://localhost/coyote3_dev/api/v1/docs
https://localhost/coyote3_dev/api/v1/auth/sessions
https://localhost/coyote3_dev/api/v1/auth/whoami
```

The backend route remains `/api/v1/...` inside the service. The reverse proxy
and FastAPI root-path configuration expose the route at the mounted public URL.

## Load-test sessions

The [self-hosted load workload](../testing/load_testing.md) uses ordinary local test
accounts and the normal session endpoints through Nginx, including `SCRIPT_NAME`.
Cookie-authenticated mutations and logout must send the login response's CSRF token;
do not disable CSRF or replace user sessions with the internal service token.
Complete required password changes before the run, scope accounts to synthetic data,
and keep rate limiting enabled unless a separately documented test requires otherwise.
Report `429` responses explicitly. Keep credentials and workload configuration in
untracked local files mounted read-only, not in results or logs. LDAP integration
checks are separate from sustained load on the application.

## Internal Service Token

Some infrastructure-only routes use `X-Coyote-Internal-Token`. That token is
configured with `INTERNAL_API_TOKEN` and is not the same as an API user session.
Do not use the internal token for normal clinical UI, Swagger, or user-scoped
automation.
