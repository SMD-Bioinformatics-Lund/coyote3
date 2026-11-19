# Coyote Core configuration

The core owns software capabilities, typed policy inputs and factory defaults.
It does not read API environment files, database credentials or deployment secrets.

## Shared permission catalog

Core packages the canonical permission definitions and built-in role templates
under `coyote/config/catalogs/rbac`. Hosts can read independent copies using
`coyote.config.governance_catalog.load_governance_catalog("permissions")` or
`load_governance_catalog("roles")`. These calls do not install records or connect
to a database. The server's explicit installation and upgrade commands consume
the same files through `RBAC_CATALOG_DIR`.

Installed role assignments, user scopes and center-created roles remain deployment
state. Built-in definitions are protected through normal administration; create
center-owned roles when different grants are required. Package imports and normal
redeployment do not reset installed state.

## Host-supplied settings

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
