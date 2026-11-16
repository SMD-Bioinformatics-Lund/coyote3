# Development

Use editable installation while changing package source:

```bash
uv sync --package coyote-demo --extra api --extra worker --extra test
```

Run tests from this directory with the workspace interpreter, using synthetic
settings and no real database connections:

```bash
../../.venv/bin/python -m pytest -m smoke
../../.venv/bin/python -m pytest
../../.venv/bin/python -m pytest --cov --cov-config=pyproject.toml
```

Tests own synthetic helpers and persistence doubles. Smoke tests inspect package
resources and disabled extension behavior without a database. Integration tests
exercise normal ingestion, permission boundaries, collision protection and
reviewed-sample preservation. Coverage includes the complete package with branch
measurement and its configured 75% floor.
