# Getting started

## Run a complete demonstration

Follow the [local and Docker demo installation](../../../docs/deployment/demo-installation.md).
It prepares dedicated databases, credentials and storage, installs the application
baseline, and starts the API, frontend and background workers. Use that procedure
to try Coyote with synthetic samples.

## Install the package into an existing demo environment

Use this option only when the isolated application is already configured. Install
the reviewed wheel and dependencies from your organization's artifact directory;
replace `/path/to/wheels` with that directory. Public PyPI publication is not required.

```bash
python -m pip install --no-index --find-links /path/to/wheels 'coyote-demo[api]==1.0.0'
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
