# Developer Task Reference

Short, repeatable workflows for common maintenance tasks.

## Run core quality checks locally

```bash
PYTHONPATH=. ruff check api coyote tests scripts
PYTHONPATH=. black --check --line-length 100 api coyote tests scripts
PYTHONPATH=. pytest -q
```

## Run focused auth typing checks

```bash
PYTHONPATH=. mypy --follow-imports=skip --ignore-missing-imports \
  api/security/auth_service.py \
  api/security/password_flows.py \
  api/infra/notifications/email.py \
  api/services/admin_user_service.py
```

## Validate compose/env wiring

```bash
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.yml config -q
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml config -q
docker compose --env-file .coyote3_dev_env -f deploy/compose/docker-compose.dev.yml config -q
docker compose --env-file .coyote3_test_env -f deploy/compose/docker-compose.test.yml config -q
```

## Build docs and validate links

```bash
python -m pip install -r requirements-docs.txt
mkdocs build --strict
```

## Read auth/mail observability lines

Structured log prefixes added for operations dashboards:

- `auth_metric ...`
- `mail_metric ...`

Examples:

- login outcomes by provider
- invite/reset token issuance outcomes
- SMTP send attempts/failures

Quick local log probes:

```bash
docker logs coyote3_api_${COYOTE3_VERSION:-local} 2>&1 | rg "auth_metric|mail_metric"
```

Follow-up operations guide:

- [Operations / Observability SLOs And Alerts](../operations/observability-slos-and-alerts.md)

## Common release checklist

1. Run full tests and lint.
2. Validate compose configs for all environments.
3. Build docs in strict mode.
4. Review env templates for placeholders only (no real secrets).
5. Split commits into `feat` / `chore(deploy)` / `docs` where possible.
