# API runtime configuration

The API owns environment loading, authentication settings, service endpoints,
storage paths and host presentation. Configure these before importing or starting
the application.

The configuration directory is `api/src/coyote_api/config/` in the repository,
or `src/coyote_api/config/` when working inside this project. The repository root
has no separate `config/` directory.

| File | Responsibility |
| --- | --- |
| `bootstrap.py` | Load `.env` and select the center profile before importing clinical contracts |
| `runtime_settings.py` | Assemble environment-derived API and worker settings |
| `backend.py` | Validate and distribute package-owned settings without forwarding the full backend configuration |
| `factory_defaults.toml` | Define host-owned fallback values |
| `application_release.toml` | Supply the generated application label independently of the API package version |
| `paths.py` | Resolve packaged assets, center files and runtime storage paths |
| `examples/center/` | Provide complete example contact, vocabulary, filter and report-presentation files |

The installed API package version is `coyote_api.version.__version__`.
`APPLICATION_VERSION` comes from the bundled application identity and supplies
product labels; environment suffixes apply to that label. The application release
workflow generates this file from its release selection before building the wheel.
It is release metadata, not a center-specific setting.

Importing `coyote_api` runs the configuration bootstrap. It reads `.env` under
`COYOTE4_RUNTIME_ROOT`, or the working directory if that variable is unset.
Already exported process variables take precedence. Named private environment
files are not discovered automatically; export a trusted file before starting
the API. Compose receives its deployment file through `--env-file` and passes
the declared settings into the containers.

The startup flow is `bootstrap.py` → `runtime_settings.py` →
`BackendSettings.from_runtime(...)` in `backend.py`. The runtime validates package
inputs before initializing infrastructure and retains the assembled settings for
its lifetime. Mongo receives `MongoSettings` and explicit logger/cache ports;
public core operations receive only `PublicSettings` availability flags. Center
policy remains an explicit `CenterConfiguration` selected before clinical contracts
are imported. Packages never receive the whole API runtime or its authentication
and email secrets.

API-only security, authentication, email and worker settings remain owned by the
host. The Python HTTP client receives its own URL and authentication inputs.
Package settings are interfaces rather than process isolation: libraries sharing
a Python process can still access its environment, even though these packages do
not discover deployment settings there.

| Setting group | Purpose |
| --- | --- |
| MongoDB URI/name pairs | Select separate application, identity, knowledgebase and BAM databases |
| Redis and Celery settings | Configure cache, broker, result backend and worker queues |
| Authentication and secrets | Configure local/LDAP authentication, sessions and service credentials |
| Storage roots | Locate report artifacts, logs and ingestion files |
| Center directory | Supply reviewed vocabulary, filter flags, contact and report presentation |

`COYOTE4_CENTER_CONFIG_DIR` selects the process's center directory.
`COYOTE4_CENTER_CONFIG_HOST_DIR` can supply the inherited host selection.
The host selects that profile before loading clinical contracts. A different
profile requires a process restart.

Assay configuration and other editable clinical resources are database-backed.
Environment settings do not replace those records on every deployment. Keep
secrets and reviewed center files outside the source tree and wheel contents.

The API reuses MongoDB connection defaults from the adapter and clinical defaults
from the core. Its own defaults are in `src/coyote_api/config/factory_defaults.toml`.
The complete environment and mount procedures are application-level deployment
references; the package does not choose a center's endpoints or credentials.
