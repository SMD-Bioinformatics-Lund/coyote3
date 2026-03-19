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

## Secrets handling

- Keep real values out of git
- Use example env files only as templates
- Rotate secrets on team membership changes
- Validate before deployment with `scripts/validate_env_secrets.sh`
