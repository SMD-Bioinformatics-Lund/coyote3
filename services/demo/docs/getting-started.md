# Getting started

Install the built wheel with its API integration dependencies:

```bash
python -m pip install 'coyote-demo[api]==1.0.0'
```

The base `coyote-demo` package supplies synthetic resources and validation without
installing the server. The `api` extra installs the matched server distribution.
Use a reviewed local demonstration configuration; the package rejects ordinary
application database targets. Complete the application baseline installation
before adding demo samples.

Set `COYOTE_DEMO_ENABLED=1` only in the isolated demonstration deployment.
The installed extension validates its settings before exposing administrative
demo routes. When disabled, installing the package adds no API routes.

Continue with [configuration](configuration.md) and [usage](usage.md).
