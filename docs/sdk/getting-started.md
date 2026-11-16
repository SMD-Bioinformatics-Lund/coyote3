# Install and use the SDK

Run installation commands from the repository root in an activated Python
environment:

```bash
python -m pip install -e core
# Install the independent HTTP client when developing it or running client tooling.
python -m pip install -e clients/python
```

This installs the library editable. Python source changes take effect after the
consuming process reloads. Changes to dependency declarations or package metadata
require reinstalling. Native library changes require the relevant native build.

For application development use the [uv workspace](uv-development.md):

```bash
uv sync --all-packages --group test --group dev --group docs
```

Deployment builds four wheels: core, server, HTTP client and ingestion service.
The API and MongoDB adapter share the server wheel. No public-index publication
is required. See [server installation](server-installation.md).

After configuring the deployment environment and databases, run
`coyote4-api --host 127.0.0.1 --port 8001`, or
`uvicorn coyote_api.app.main:app --host 127.0.0.1 --port 8001`.
See [server installation](server-installation.md) for boundaries and resources.

## Choose an entry point

Use `coyote_pyclient.CoyoteClient` for a notebook, external script or integration
that accesses an existing deployment. Authentication, authorization and database
access stay on the server. See the [remote client guide](python-client.md) for
login, attribute access, pagination, mutations and error handling.

Use `coyote.application.operations` when building a trusted application host or
worker. The host supplies verified authentication, current authorization policy,
storage and integration capabilities. Installing the library does not supply
those capabilities or create an authenticated application. See
[application operations](application-sdk.md) and [SDK development](extending.md).

## Explicit center configuration

Library imports ignore `COYOTE4_CENTER_CONFIG_HOST_DIR`, `COYOTE4_CENTER_CONFIG_DIR`,
`.env`, API secrets and database connection variables. A standalone host can select
an external profile explicitly:

```python
from pathlib import Path

from coyote.config import CenterConfiguration, configure_center

configure_center(CenterConfiguration(directory=Path("/etc/coyote4/center")))

# Import operations after selecting the profile.
from coyote.application.operations import CoyoteApplication
```

The library requires `clinical_vocabulary.toml` and `filter_flag_metadata.yaml`.
The API host additionally requires `contact.toml` for its public contact page;
contact content is not an SDK input. The API/worker host selects the directory
from deployment settings before importing library contracts. Each owner validates
its configuration before runtime work starts.

One process uses one center profile. Contract definitions depend on that profile,
so changing it requires a process restart. A late profile switch fails explicitly.
Without an explicit profile, standalone operations use packaged software defaults.
Center examples live under `api/src/coyote_api/config/examples/center/`; persistent deployment files
live outside the checkout. See [center configuration](../deployment/center-configuration.md).

## Inspect the installed version

```python
from importlib.metadata import version

print(version("coyote-core"))
```

This is the SDK version. The complete application's release version is separate;
see [versions and compatibility](compatibility.md).
