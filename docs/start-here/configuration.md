# Configuration Model

## Environment files

- `.coyote3_env` (prod-style)
- `.coyote3_stage_env` (stage)
- `.coyote3_dev_env` (dev)
- `.coyote3_test_env` (test stack and CI-like local runs)

Template sources:

- `deploy/env/example.prod.env`
- `deploy/env/example.stage.env`
- `deploy/env/example.dev.env`
- `deploy/env/example.test.env`

## Critical variables

Security-sensitive:

- `SECRET_KEY`
- `COYOTE3_FERNET_KEY`
- `INTERNAL_API_TOKEN`
- `MONGO_ROOT_USERNAME`
- `MONGO_ROOT_PASSWORD`
- `MONGO_APP_USER`
- `MONGO_APP_PASSWORD`

Core runtime:

- `COYOTE3_DB`
- `MONGO_URI`
- `COYOTE3_WEB_PORT`
- `COYOTE3_API_PORT`
- `COYOTE3_REDIS_PORT`

## Strict behavior by profile

Production and development should require explicit secrets. Test profile may use fixed CI-safe values.

Validate env quickly:

```bash
bash scripts/validate_env_secrets.sh .coyote3_env
bash scripts/validate_env_secrets.sh .coyote3_stage_env
bash scripts/validate_env_secrets.sh .coyote3_dev_env
```
