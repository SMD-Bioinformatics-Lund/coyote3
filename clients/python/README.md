# Coyote3 Python HTTP client

Install independently of the server and application SDK:

```bash
pip install coyote3-client
```

Version 1.0.0 uses `CoyoteClient` and `AsyncCoyoteClient` for all authentication and
HTTP operations; see [version compatibility](../../docs/sdk/compatibility.md#python-client-10-authentication).

```python
from coyote3_client import CoyoteClient

with CoyoteClient("https://coyote3.example.test") as client:
    client.login(username="reviewer", password="your-password", provider="local")
    sample = client.samples.get("SYNTHETIC_SAMPLE")
    variants = sample.variants.tiered_variants()
    trial = sample.reports.try_new("dna")
```

`AsyncCoyoteClient` provides awaitable authentication, resource reads, clinical
analysis methods, report operations and general API endpoints through HTTPX.
Both clients use explicit timeouts, TLS verification and server-provided errors.
Authorization remains on the server; the client never imports `api` or `coyote3`.

The server's OpenAPI contract is authoritative. Repository contract tests check
the resource paths against the actual FastAPI specification. Additive endpoint
access is available through `client.api`; its fluent attributes construct paths
and do not imply that a server endpoint exists.

For source development use `pip install -e clients/python` from the repository
root. The former `coyote3.client` import becomes `coyote3_client`; the independent
distribution retains the synchronous resource methods and response models.

This independent client is distributed under [Apache License 2.0](LICENSE.txt).
See [NOTICE.txt](NOTICE.txt) for ownership and attribution. The COYOTE3 application
SDK and server have a separate license; their implementation is not included here.
