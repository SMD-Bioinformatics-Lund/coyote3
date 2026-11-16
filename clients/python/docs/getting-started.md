# Install and use the HTTP client

Python 3.12 or newer is required. Install a retained `coyote_pyclient` wheel,
or install this project from its own directory:

```bash
python -m pip install .
```

Supply the public deployment URL, including any mount prefix and excluding
`/api/v1`. The following example makes network requests and requires an account
on that deployment:

```python
import os
from coyote_pyclient import CoyoteClient

with CoyoteClient(os.environ["COYOTE_URL"]) as client:
    client.login(
        username=os.environ["COYOTE_USERNAME"],
        password=os.environ["COYOTE_PASSWORD"],
        provider="local",
    )
    sample = client.samples.get("SYNTHETIC_SAMPLE")
```

The sample identifier is illustrative. The server must contain the requested
sample and permit access. Continue with [resource usage](usage.md) and
[transport configuration](configuration.md).
