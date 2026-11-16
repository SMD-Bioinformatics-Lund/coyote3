# Configuration

Demo installation requires explicit settings. No database endpoint is inferred
from another database or from an ordinary deployment.

| Setting | Required value |
| --- | --- |
| `COYOTE_DEMO_ENABLED` | `1` |
| `COYOTE_DEMO_MODE` | `docker` or `native` |
| `ENV_NAME` | `testing` |
| `COYOTE4_RUNTIME_MODE` | `production`, retaining normal authentication and security |
| `COYOTE4_DB` | `coyote4_demo` |
| `IDENTITY_DB` | `coyote4_demo_identity` |
| `KNOWLEDGEBASE_DB` | `coyote4_demo_knowledgebase` |
| `BAM_DB` | `coyote4_demo_bam` |
| `AUTHENTICATION_PROVIDERS` | `local` |

All four MongoDB URI settings must be explicit, authenticated replica-set
connections using the restricted `coyote_demo` user. Native mode requires
loopback endpoints; Docker mode requires `demo-mongo:27017`. Expanded database
privileges are checked before installation and must cover only the demo databases.

Use separate authenticated Redis URLs for cache, broker and results. Disable
LDAP, SMTP, GENS, IGV and public OncoKB/ClinPGx lookups. `PUBLIC_BASE_URL` must be a
local HTTP address. Credentials belong in an untracked deployment environment,
never in package resources or demo manifests.

The optional `worker` extra supplies the Relay worker integration. Start it with
`python -m coyote_demo.runtime ingest`; this entry point validates the demo targets and
credential scope before importing or starting the queue consumer. Installation
does not start a worker automatically.
