# Engineering command reference

Use this page for common development and release commands. The
[complete developer manual](../developer/complete_developer_manual.md) explains
the architecture, data flow, extension points, and development rules.

## Local checks

Run commands from the repository root with the project virtual environment
active.

| Check | Command |
| --- | --- |
| Python lint | `PYTHONPATH=. ruff check api tests scripts` |
| Python formatting | `ruff format --check api tests scripts` |
| Python types | `PYTHONPATH=. mypy` |
| Backend tests | `PYTHONPATH=. pytest -q` |
| Frontend lint | `npm --prefix frontend run lint` |
| Frontend unit tests | `npm --prefix frontend run test:unit` |
| Frontend build | `npm --prefix frontend run build` |
| Browser tests | `npm --prefix frontend run test:e2e` |
| Markdown lint | `npm run docs:lint` |
| Documentation build | `.venv/bin/python -m mkdocs build --strict` |

The strict mypy boundary is configured in `pyproject.toml`. Add a module only
after it passes the existing strict settings. Do not weaken a type rule to make
new code pass.

## Compose validation

Validate the resolved Compose model before changing deployment files.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  config -q

./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  config -q
```

Use the equivalent environment file and override for staging or testing.

## Logs

API logs are structured JSON. Authentication and mail outcomes use the
`auth_metric` and `mail_metric` event names.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  logs api 2>&1 | rg "auth_metric|mail_metric"
```

## Before opening a pull request

| Area | Required result |
| --- | --- |
| Behavior | Tests cover the success path, rejection path, and changed permission boundary. |
| Contracts | Generated contract documentation matches the Pydantic schemas. |
| Frontend | Lint, unit tests, build, and affected browser tests pass. |
| Documentation | Markdown lint, link checks, and the strict MkDocs build pass. |
| Deployment | Changed Compose combinations resolve successfully. |
| Security | No credentials, clinical identifiers, or local environment files are staged. |
| Commits | Each commit contains one coherent change. |
