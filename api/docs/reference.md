# API component reference

| Entry point or module | Purpose |
| --- | --- |
| `coyote4-api` | Console launcher with host, port and worker options |
| `coyote_api.app.main:app` | ASGI application |
| `coyote_api.app.main.create_api_app` | Application factory |
| `coyote_api.celery_app` | Task publication, maintenance workers and beat configuration |
| `coyote_api.version` | Server distribution version, bundled application label and selected core version |
| `coyote_api.interfaces.http.v1` | Version-one HTTP routes |
| `coyote_api.security` | Host authentication and authorization adaptation |
| `coyote_api.app.application_factory` | Composition of core operations |
| `coyote_api.bootstrap.paths` | Packaged installation-catalog locations |

The distribution is `coyote-server`; the API's Python namespace is `coyote_api`.
The same distribution also contains `coyote_mongo`.
The executable retains the application name `coyote4-api`.

The running application's OpenAPI document describes its HTTP operations and
schemas. Packaged Python modules support the host; they are not an alternative
public HTTP contract. Existing `/api/v1` paths do not depend on source-directory
names.

[Resource metadata reads](resource-reads.md) documents the authenticated retrieval
endpoint, fields, filters, related records and pagination limits.

`GET /api/v1/users/session-activity` returns aggregate login counts to superusers
only. It reports distinct signed-in users, valid sessions, recently active users,
the activity window in seconds and the observation time in UTC. The response is
not cacheable. Counts cover the configured identity store, including other
deployments that share it; service tokens are not browser login sessions.
