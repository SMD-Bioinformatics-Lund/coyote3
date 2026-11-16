# Client configuration

| Input | Behavior |
| --- | --- |
| `base_url` | Public HTTP(S) origin and optional mount prefix, without `/api/v1` |
| `timeout` | HTTP timeout in seconds; default 30 |
| `cookie_name` | Server session cookie name; default `coyote4_api_session` |
| `transport` | Optional HTTPX transport for tests; ordinary calls use HTTP transport |

URLs containing credentials, a query or a fragment are rejected. Keep credentials
out of URLs and source files. HTTPS certificate verification remains enabled.

Use `login(username=..., password=..., provider=...)` for account authentication
or `login_with_token(...)` for a supported existing token. The server checks
current account state and permissions; constructing a client grants no access.

Use the client as a context manager so its HTTP connection pool is closed.
The asynchronous client supports `async with` and awaited operations.
Tests can inject HTTPX mock transports without contacting a server.
