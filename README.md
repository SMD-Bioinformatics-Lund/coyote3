# Coyote3

Coyote3 is a clinical genomics platform for DNA/RNA interpretation and reporting.

- Flask UI (`coyote/blueprints`) for user workflows
- FastAPI backend (`api/routers`, `api/services`, `api/core`) for business logic and policy
- MongoDB for persistent data
- Redis for cache/session support

## Documentation

Primary documentation is in `docs/` and rendered via MkDocs.

Start here:

- [Quickstart](docs/start-here/quickstart.md)
- [Local Development](docs/start-here/local-development.md)
- [UI Map And User Flows](docs/product/ui-map-and-user-flows.md)
- [Ingestion API](docs/api/ingestion-api.md)
- [Deployment Runbook](docs/operations/deployment-runbook.md)
- [Testing And Quality](docs/testing/testing-and-quality.md)

## Fast setup

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp deploy/env/example.dev.env .coyote3_dev_env
./scripts/compose-with-version.sh --env-file .coyote3_dev_env -f deploy/compose/docker-compose.dev.yml up -d --build
```

## Local quality checks

```bash
bash scripts/setup_git_hooks.sh
PYTHONPATH=. python -m ruff check api coyote tests scripts
PYTHONPATH=. python -m pytest -q
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```
