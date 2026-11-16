# Frontend configuration

Vite reads presentation and development-proxy settings from its process environment.

| Setting | Purpose |
| --- | --- |
| `COYOTE4_API_INTERNAL_URL` | Development proxy target; default `http://api:8001` |
| `SCRIPT_NAME` | Optional public mount prefix |
| `PUBLIC_BASE_URL` | Public URL used for hostname-related development settings |
| `ORGANIZATION_NAME` | Displayed organization; default `Coyote4` |
| `LOCAL_TIME_ZONE` / `TZ` | Display timezone selection; otherwise UTC |
| `ENV_NAME` | Environment label; otherwise development |
| `GENS_URI`, `IGV_URI`, `IGV_DATA_ROOT` | Optional integration locations |

Requests under the mounted `/api` path are forwarded to the configured proxy
target. The proxy strips the mount prefix when needed. Configure the URL for the
environment where Vite actually runs; a container hostname is not automatically
resolvable from a host process.

Application version comes from the root `release.toml`. These inputs are used
during development startup or production build; changing them requires restarting
the development server or rebuilding the static application.

Browser-visible configuration must not contain database credentials, signing
secrets or private service tokens. Authentication and permission policy belong
to the API.
