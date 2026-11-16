# Configuration

Offline commands read only the selected bundle directory. Atlas does not discover
or load application `.env` files.

| Setting | CLI option | Environment variable |
| --- | --- | --- |
| API origin and optional deployment prefix | `--api-url` | `COYOTE_ATLAS_API_URL` |
| Existing administrator session token | `--token-env NAME` selects a variable | `COYOTE_ATLAS_TOKEN` by default |
| Trusted private certificate authority | `--ca-bundle` | `COYOTE_ATLAS_CA_BUNDLE` |
| Reviewed package identity | `--expected-manifest-sha256` required | None |
| Controlled bundled repair | `--force` | None |

Explicit CLI settings override environment values. Selecting a missing token
variable fails rather than falling back to another credential. The token is read
from the environment and is never printed or accepted as a command-line value.
API URLs may include a deployment prefix, but cannot contain credentials, query
parameters or fragments. HTTPS certificate verification remains enabled.

Host database URIs, physical collection names, credentials and audit configuration
belong to the server and its adapters. Atlas's standalone commands do not need
those settings. Installing the optional API integration uses the already configured
server; it does not create another runtime or load a second environment file.
