# Install and use the SDK

Run installation commands from the repository root in an activated Python
environment:

```bash
python -m pip install -e .
# Install the independent HTTP client when developing it or running client tooling.
python -m pip install -e clients/python
```

This installs the library editable. Python source changes take effect after the
consuming process reloads. Changes to dependency declarations or package metadata
require reinstalling. Native library changes require the relevant native build.

For application development, install `requirements-dev.txt` as well. For a server
installation use `pip install "coyote3[api]"`; for all declared extras use
`pip install "coyote3[all]"`. The same wheel contains core and API modules; extras
select dependencies. Deployment images install that wheel normally. The remote
client installs independently with `pip install coyote3-client`.

After configuring the deployment environment and databases, run
`coyote3-api --host 127.0.0.1 --port 8001`, or
`uvicorn api.app.main:app --host 127.0.0.1 --port 8001`.
See [server installation](server-installation.md) for boundaries and resources.

## Choose an entry point

Use `coyote3_client.CoyoteClient` for a notebook, external script or integration
that accesses an existing deployment. Authentication, authorization and database
access stay on the server. See the [remote client guide](python-client.md) for
login, attribute access, pagination, mutations and error handling.

Use `coyote3.application.operations` when building a trusted application host or
worker. The host supplies verified authentication, current authorization policy,
storage and integration capabilities. Installing the library does not supply
those capabilities or create an authenticated application. See
[application operations](application-sdk.md) and [SDK development](extending.md).

## Explicit center configuration

Library imports ignore `COYOTE3_CENTER_CONFIG_DIR`, `.env`, API secrets and database
connection variables. A standalone host can select an external profile explicitly:

```python
from pathlib import Path

from coyote3.config import CenterConfiguration, configure_center

configure_center(CenterConfiguration(directory=Path("/etc/coyote3/center")))

# Import operations after selecting the profile.
from coyote3.application.operations import CoyoteApplication
```

The library requires `clinical_vocabulary.toml` and `filter_flag_metadata.yaml`.
The API host additionally requires `contact.toml` for its public contact page;
contact content is not an SDK input. The API/worker host selects the directory
from deployment settings before importing library contracts. Each owner validates
its configuration before runtime work starts.

One process uses one center profile. Contract definitions depend on that profile,
so changing it requires a process restart. A late profile switch fails explicitly.
Without an explicit profile, standalone operations use packaged software defaults.
Center examples live under `config/examples/center/`; persistent deployment files
live outside the checkout. See [center configuration](../deployment/center-configuration.md).

## Inspect the installed version

```python
from importlib.metadata import version

print(version("Coyote3"))
```

This is the SDK version. The complete application's release version is separate;
see [versions and compatibility](compatibility.md).
