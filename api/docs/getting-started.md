# Install and start the API

Python 3.12 or newer is required. Application images use Python 3.14.7.
Install `coyote-server` with the core version declared in the repository root's
`pyproject.toml`. The server distribution includes the API and MongoDB adapter.
Use retained wheels or the repository workspace; the packages need not be
published to PyPI.

For repository development:

```bash
uv sync --all-packages --group dev --group test --group docs
uv run --package coyote-server uvicorn coyote_api.app.main:app \
  --host 127.0.0.1 --port 8001 --reload \
  --reload-dir core/src --reload-dir api/src --reload-dir adapters/mongo/src
```

Configure the [runtime settings](configuration.md) before starting the process.
Starting the server requires the configured services; installing the package
does not provision MongoDB, Redis, users or a center profile.

For an installed application, the console entry point is:

```bash
coyote4-api --host 127.0.0.1 --port 8001 --workers 1
```

Listener addresses are explicit. Expose the application through its deployment's
proxy and security configuration rather than using the development reload server.
