# Environments And Secrets

## Environment separation

Use isolated stacks and databases for each environment:

- **prod**: `deploy/compose/docker-compose.yml`
- **stage**: `deploy/compose/docker-compose.stage.yml`
- **dev**: `deploy/compose/docker-compose.dev.yml`

## Default port matrix

| Environment | Web | API | Redis | Mongo |
| --- | --- | --- | --- | --- |
| prod | 5816 | 5818 | 5819 | 5820 |
| stage | 8805 | 8806 | 8807 | 8808 |
| dev | 6801 | 6802 | 6803 | 6804 |
| test | 6811 | 6812 | 6813 | 6814 |

These defaults are encoded in both compose files and example env templates.

## Redis runtime policy

- All compose stacks pin Redis to `redis:7.4.3`.
- Redis is a shared cache dependency for API/UI and should be treated as required
  in production-grade deployments (`CACHE_REQUIRED=1`).
- If a center intentionally runs in degraded mode (`CACHE_REQUIRED=0`), cache
  operations become no-op on Redis outages; functionality should still work but
  with lower performance.

## Environment naming map

Runtime profile normalization:

- `production` -> `production`
- `development` / `dev` -> `development`
- `test` / `testing` -> `test`
- `validation` / `stage` / `staging` -> `validation`

Use `validation` in persisted profile fields for stage/staging environments.

## Database isolation

Recommended:

- separate Mongo instance per environment
- same DB name (`coyote3`) is acceptable with isolated instances
- app user credentials per environment

## Mongo credential roles

- `MONGO_ROOT_*`: bootstrap/admin operations
- `MONGO_APP_*`: application runtime access (least privilege)
- Compose mongo-init creates `MONGO_APP_*` only on first startup of an empty Mongo volume
- If volume already exists, create/rotate app user with `scripts/mongo_bootstrap_users.py`

Example (existing volume/user rotation):

```bash
python scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## Secrets handling

- Keep real values out of git
- Use example env files only as templates
- Rotate secrets on team membership changes
- Validate before deployment with `scripts/validate_env_secrets.sh`

## SMTP relay strategy

Preferred center-safe baseline is external SMTP relay (no host Postfix coupling):

```env
SMTP_HOST='mxis.skane.se'
SMTP_PORT='25'
SMTP_USE_TLS='0'
SMTP_USE_SSL='0'
SMTP_USERNAME=''
SMTP_PASSWORD=''
SMTP_FROM_EMAIL='CHANGE_ME_FROM_EMAIL'
```

Behavior guarantees:

- User create/invite/reset flows do not hard-fail if mail cannot be delivered.
- API/UI return warning + manual setup URL metadata when email send fails.
- This keeps admin workflows functional even when SMTP is temporarily unavailable.
