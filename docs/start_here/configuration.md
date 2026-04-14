# Configuration And Environments

This document describes how Coyote3 configuration is organized across environments.

## Environment Files

Application behavior is controlled by environment files (`.coyote3_env*`). Templates live in `deploy/env/`:

- **Production**: Managed via `.coyote3_env` (Ref: `example.prod.env`).
- **Staging**: Managed via `.coyote3_stage_env` (Ref: `example.stage.env`).
- **Development**: Managed via `.coyote3_dev_env` (Ref: `example.dev.env`).
- **Continuous Validation**: Managed via `.coyote3_test_env` (Ref: `example.test.env`).

Use these templates as the starting point for each environment.

## Default Port Layout

The platform uses separate host-port ranges to avoid collisions between environments:

| Domain Layer | Production | Staging | Development | Test/CI |
| --- | --- | --- | --- | --- |
| **Edge Proxy** | `5815` | `8804` | n/a | n/a |
| **Web UI** | `5816` | `8805` | `6801` | `6811` |
| **REST API** | `5818` | `8806` | `6802` | `6812` |
| **Documentation** | `5821` | `8809` | `6805` | `6815` |
| **Redis Cache** | `5819` | `8807` | `6803` | `6813` |
| **Durable Store** | `5820` | `8808` | `6804` | `6814` |

## Critical Configuration Parameters

### Cryptographic And Identity Secrets
These parameters are security-sensitive. They should be unique per environment and must not be committed to version control:
- `SECRET_KEY`: Primary cryptographic anchor for session signing and data protection.
- `INTERNAL_API_TOKEN`: Shared secret for service-to-service requests.
- `PASSWORD_TOKEN_SALT`: Cryptographic salt for user lifecycle link generation.
- `MONGO_APP_PASSWORD`: Identity secret for least-privilege database access.

### Core Execution Definitions
- `MONGO_URI`: Connection string for MongoDB.
- `CACHE_REDIS_URL`: Connection string for Redis.
- `API_WORKERS`: Worker count for the FastAPI service.
- `WEB_APP_BASE_URL`: Public web URL used for generated links.
- `HELP_CENTER_URL`: Documentation or help URL shown in the web UI.

## Caching

Coyote3 uses a layered caching model:
- **Hot Tier (Redis)**: Shared request/session-adjacent cache data.
- **Warm Tier (MongoDB)**: Stored snapshots of dashboard or summary data.
- **Cache Requirements**: `CACHE_REQUIRED` controls whether Redis failure is fatal or tolerated.

### Dashboard Cache Tuning
The following settings control dashboard cache freshness and retention:
- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS`: Maximum age for localized hot-cache data.
- `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS`: Refresh threshold for persistent Mongo snapshots.
- `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`: Physical retention period for historical dashboard data.

## Access Control And Identity

The platform supports multiple authentication providers and keeps local and centralized authentication separate.

### Role Levels
Assigned role levels provide the baseline for permission evaluation.

| Role Designation | Access Level | Professional Scope |
| --- | --- | --- |
| `viewer` | `5` | Unprivileged clinical oversight. |
| `user` | `9` | Standard diagnostic interpretation and reporting. |
| `manager` | `99` | Departmental oversight and review. |
| `admin` | `99999` | System-wide configuration and security control. |

### Identity Normalization
Login identifiers are normalized to reduce duplicates and mismatches:
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
