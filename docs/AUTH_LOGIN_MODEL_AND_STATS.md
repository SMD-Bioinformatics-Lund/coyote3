# Authentication Login Modes and Runtime Stats

## 1. Scope
This document explains how Coyote3 login works in current runtime, with emphasis on:
- LDAP-backed enterprise users
- local allowlisted users for controlled offline/dev operation
- internal service token usage for internal endpoints

It also provides measured login/user distribution stats from the active dev snapshot.

## 2. Authentication flows
## 2.1 UI login flow
1. Browser submits login form to Flask (`/login`).
2. Flask calls API `POST /api/v1/auth/login`.
3. API validates credentials.
4. API returns session token and sets API session cookie.
5. Flask stores lightweight user session payload and forwards API session token on server-side API calls.

## 2.2 API session handling
- API session cookie: `coyote3_api_session` (default)
- Flask forwards `Authorization: Bearer <session_token>` to API for server-side calls.
- If API session token is missing/invalid, request must be treated as unauthenticated.

## 2.3 LDAP login path
For non-allowlisted users, API auth delegates to LDAP via configured LDAP manager.

## 2.4 Local login path (allowlisted)
For explicitly allowlisted identities (dev/test/admin set), API validates stored password hash in Mongo.

Local path is used when either condition is true:
- `auth_type == "coyote3"`
- identity matches `LOCAL_AUTH_USER_IDENTIFIERS` allowlist

## 2.5 Internal API token path
Internal utility endpoints (`/api/v1/internal/*`) require internal token header validation and are not user-session endpoints.

## 3. Runtime configuration keys
Important keys:
- `LOCAL_AUTH_USER_IDENTIFIERS`
- `LDAP_HOST`, `LDAP_BASE_DN`, `LDAP_USER_LOGIN_ATTR`
- `SECRET_KEY`, `API_SESSION_SALT`
- `API_SESSION_COOKIE_NAME`, `API_SESSION_TTL_SECONDS`
- `SESSION_COOKIE_SECURE` (must be secure in production)

## 4. Current measured auth distribution (dev snapshot)
Measured on: `2026-03-11`
Database: `coyote_dev_3`

User distribution:
- total users: `34`
- active users: `34`
- `auth_type=coyote3`: `10`
- `auth_type=ldap`: `24`
- allowlisted local-auth identities: `9`
- non-allowlisted identities: `25`

Operational interpretation:
- LDAP remains dominant for enterprise users.
- Local allowlist supports controlled dev/offline access and selected test/admin identities.

## 5. How to recalculate stats

```python
from pymongo import MongoClient
from collections import Counter

c = MongoClient("mongodb://localhost:37017")
db = c["coyote_dev_3"]
users = list(db["users"].find({}, {"_id":1, "email":1, "auth_type":1, "is_active":1}))

allow = {
  "coyote3.admin", "coyote3.admin@skane.se", "coyote3.demo", "coyote3.demo@skane.se",
  "coyote3.developer", "coyote3.developer@skane.se", "coyote3.external", "coyote3.external@skane.se",
  "coyote3.intern", "coyote3.intern@skane.se", "coyote3.manager", "coyote3.manager@skane.se",
  "coyote3.tester", "coyote3.tester@skane.se", "coyote3.user", "coyote3.user@skane.se",
  "coyote3.viewer", "coyote3.viewer@skane.se",
}

cnt = Counter()
for u in users:
    auth = (u.get("auth_type") or "ldap").lower()
    cnt[f"auth_type:{auth}"] += 1
    cands = {str(u.get("_id","")).lower(), str(u.get("email","")).lower()}
    cnt["allowlisted_local_auth" if (cands & allow) else "non_allowlisted"] += 1
    cnt["active" if u.get("is_active", True) else "inactive"] += 1

print("total_users", len(users))
for k in sorted(cnt):
    print(k, cnt[k])
```

## 6. Security and operations notes
## 6.1 Local allowlist is controlled scope only
Allowlisted local accounts are for dev/test/operational continuity where LDAP may be unavailable. Keep allowlist explicit and reviewed.

## 6.2 Production recommendation
- Minimize local-auth identities in production.
- Prefer LDAP-backed identities for normal operations.
- Protect `LOCAL_AUTH_USER_IDENTIFIERS` via controlled env management.

## 6.3 Session consistency requirement
UI session and API session must not drift. If API session token is absent/invalid, Flask user context should be cleared and login required again.

## 6.4 Audit posture
API is authoritative for auth and access decisions. Login failures, denies, and privileged route access must remain observable in API/web logs with request correlation fields.

## 7. Troubleshooting login quickly
1. Verify API health (`/api/v1/health`).
2. Verify active DB name in `.coyote3_dev_env` (`COYOTE3_DB_NAME`).
3. Confirm user exists in active DB (`users` and, when used, `users_beta2`).
4. Validate local-auth hash and `auth_type` for allowlisted users.
5. Confirm API session cookie presence after login.
6. Inspect API logs for `401 Invalid credentials` vs `401 Login required`.
