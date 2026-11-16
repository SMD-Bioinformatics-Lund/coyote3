# Core configuration

The core owns software capabilities, typed policy inputs and factory defaults.
It does not read API environment files, database credentials or deployment secrets.

Anonymous catalog operations accept `coyote.config.public.PublicSettings` with
reference-service availability flags. They do not receive reference-service URLs,
database credentials or the backend settings dictionary. Hosts construct this
model explicitly alongside the center profile.

A host may select an external center profile before importing operations:

```python
from pathlib import Path
from coyote.config import CenterConfiguration, configure_center

configure_center(
    CenterConfiguration(directory=Path("/etc/coyote4/center"))
)

# Import profile-dependent contracts after selection.
from coyote.application.operations import CoyoteApplication
```

The directory must contain `clinical_vocabulary.toml` and
`filter_flag_metadata.yaml`. A supplied `manifest.json` must use the supported
center-configuration format. Missing or invalid files fail explicitly.

One process uses one immutable profile. Contracts bind to that profile when
loaded; switching profiles later requires a process restart. Without explicit
selection, the core uses its packaged defaults.

Assays, gene lists, published rules and user settings are persisted resources
supplied through repositories. Installing a new core wheel does not itself
replace those records. Contact details and report-branding paths belong to the
application host, not to core profile selection.
