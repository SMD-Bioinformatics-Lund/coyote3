# Enterprise Configuration and Environment Architecture

This document serves as the authoritative specification for platform configuration management. Coyote3 utilizes a strictly environment-aware configuration model, isolating and enforcing operational parameters across development, staging, and production runtimes.

## Environment Domain Partitioning

Application behavior is governed by targeted environment files (`.coyote3_env*`). Standardized templates are maintained within `deploy/env/` to ensure structural parity and secure credential management:

- **Production**: Managed via `.coyote3_env` (Ref: `example.prod.env`).
- **Staging**: Managed via `.coyote3_stage_env` (Ref: `example.stage.env`).
- **Development**: Managed via `.coyote3_dev_env` (Ref: `example.dev.env`).
- **Continuous Validation**: Managed via `.coyote3_test_env` (Ref: `example.test.env`).

Each configuration template serves as the non-negotiable schema for its respective profile. Centers must utilize these templates to provision localized environment files.

## Deterministic Network Topology

The platform assigns non-overlapping host-port ranges to prevent environmental collisions in shared hosting contexts:

| Domain Layer | Production | Staging | Development | Test/CI |
| --- | --- | --- | --- | --- |
| **Edge Proxy** | `5815` | `8804` | n/a | n/a |
| **Web UI** | `5816` | `8805` | `6801` | `6811` |
| **REST API** | `5818` | `8806` | `6802` | `6812` |
| **Documentation** | `5821` | `8809` | `6805` | `6815` |
| **Redis Cache** | `5819` | `8807` | `6803` | `6813` |
| **Durable Store** | `5820` | `8808` | `6804` | `6814` |

## Critical Configuration Parameters

### Cryptographic and Identity Secrets
The following parameters are mission-critical for system security. These must be randomized per environment and excluded from all version control:
- `SECRET_KEY`: Primary cryptographic anchor for session signing and data protection.
- `INTERNAL_API_TOKEN`: Shared secret for localized service-to-service orchestration.
- `PASSWORD_TOKEN_SALT`: Cryptographic salt for user lifecycle link generation.
- `MONGO_APP_PASSWORD`: Identity secret for least-privilege database access.

### Core Execution Definitions
- `MONGO_URI`: Authoritative connection string for the persistent database cluster.
- `CACHE_REDIS_URL`: Endpoint for unified Redis-based caching and state synchronization.
- `API_WORKERS`: Configurable worker count for high-performance FastAPI orchestration.
- `WEB_APP_BASE_URL`: Mandated public-facing URI for identity link generation.
- `HELP_CENTER_URL`: Defined endpoint for the standalone enterprise help environment.

## Caching Architecture and Persistence

Coyote3 employs a multi-tier caching strategy to optimize diagnostic performance:
- **Hot Tier (Redis)**: Managed per-identity request caching for rapid interpretive views.
- **Warm Tier (MongoDB)**: Persisted snapshots of complex analytic rollups and dashboard states.
- **Cache Requirements**: The `CACHE_REQUIRED` directive controls the platform's behavior during Redis failure (Fail-fast vs. Degraded execution).

### Analytics Performance Tuning
To ensure data freshness and system responsiveness, the platform enforces strict TTL boundaries:
- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS`: Maximum age for localized hot-cache data.
- `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS`: Refresh threshold for persistent Mongo snapshots.
- `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`: Physical retention period for historical dashboard data.

## Access Control and Identity Governance

The platform supports a provider-aware identity model, enforcing strict separation between local and centralized authentication sources.

### Role-Based Access Level (RBAC) Standards
Assigned role levels provide the baseline for system-wide permission evaluation.

| Role Designation | Access Level | Professional Scope |
| --- | --- | --- |
| `viewer` | `5` | Unprivileged clinical oversight. |
| `user` | `9` | Standard diagnostic interpretation and reporting. |
| `manager` | `99` | Departmental oversight and review. |
| `admin` | `99999` | System-wide configuration and security control. |

### Identity Normalization
To prevent credential fragmentation, the platform enforces mandatory normalization of login identifiers:
- All email-style identifiers are normalized to lowercase.
- Validation requires explicit local and domain segment definitions to ensure organizational compatibility.

## Service Integration Guidelines

### SMTP and Communication
Standardized mail relay configurations forSkåne (MXIS) are established as the organizational baseline:
- `SMTP_HOST`: Standardized relay host `mxis.skane.se`.
- `SMTP_PORT`: Standardized port `25` (Unauthenticated).
- `SMTP_FROM_EMAIL`: Authorized organizational sender address.

### External Analytic Integrations
The platform enables optional one-way deep-linking to secondary analytic platforms such as Gens and IGV through the `GENS_URI` and `IGV_URI` directives.

## Environmental Verification

To ensure configuration compliance, environment files must be verified against the project security schema before deployment:

```bash
# Execute environment configuration validation
bash scripts/validate_env_secrets.sh .coyote3_env
```

*For comprehensive operational maintenance protocols and seeding verification, refer to the [Operations / Maintenance and Quality](../operations/maintenance_and_quality.md) documentation.*
