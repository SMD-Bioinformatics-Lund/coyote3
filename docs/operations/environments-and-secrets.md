# Environments And Secrets

## Environment separation

Use isolated stacks and databases for each environment:

- **prod**: `deploy/compose/docker-compose.yml`
- **stage**: `deploy/compose/docker-compose.stage.yml`
- **dev**: `deploy/compose/docker-compose.dev.yml`

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
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8008}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## Secrets handling

- Keep real values out of git
- Use example env files only as templates
- Rotate secrets on team membership changes
- Validate before deployment with `scripts/validate_env_secrets.sh`
