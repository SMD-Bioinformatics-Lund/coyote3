# Editable development with uv

The repository is one uv workspace with four independently buildable packages:

| Project | Distribution | Import | Version owner |
| --- | --- | --- | --- |
| `core` | `coyote-core` | `coyote` | `core/pyproject.toml` |
| `adapters/mongo` | `coyote-mongo` | `coyote_mongo` | Its `pyproject.toml` |
| `api` | `coyote-api` | `coyote_api` | Its `pyproject.toml` |
| `clients/python` | `coyote-pyclient` | `coyote_pyclient` | Its `pyproject.toml` |

Workspace dependencies come from this checkout, not a public package index.
uv installs workspace members editable. One lockfile resolves their dependencies
together; separate wheel builds retain each package's own metadata. The root
`pyproject.toml` is a virtual workspace with shared development dependency groups;
it does not build a distribution. Every member owns its `src/`, tests and docs.

## Set up once

Use Python 3.14.7 for the application environment. Install uv using the
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root:

```bash
uv sync --all-packages --group test --group dev --group docs
```

This creates or synchronizes `.venv`. It may remove packages installed manually
that are outside the selected workspace dependencies. Keep optional load tools
in their documented separate environment.

## Edit and run

```bash
uv run --package coyote-api uvicorn coyote_api.app.main:app \
  --host 127.0.0.1 --port 8001 --reload \
  --reload-dir core/src --reload-dir api/src --reload-dir adapters/mongo/src
```

Supply the existing environment configuration before starting the API. This
command does not launch MongoDB, Redis or workers.

Changes to core, adapter and API Python files are loaded when Uvicorn restarts
the process. Do not rebuild wheels for ordinary Python edits. Restart workers
after changing imported code; Celery does not inherit Uvicorn's reload behavior.
Run `uv sync` again after changing dependencies, versions or entry points.

Frontend development remains separate:

```bash
npm --prefix frontend run dev
```

## Run tests

```bash
scripts/quality/run_package_tests.sh core
scripts/quality/run_package_tests.sh mongo
scripts/quality/run_package_tests.sh api
scripts/quality/run_package_tests.sh client
scripts/quality/run_package_tests.sh all --smoke
scripts/quality/run_package_tests.sh all --coverage
uv run --package coyote-api pytest tests
uv run --package coyote-api pytest
```

Package suites exercise their own contracts. The shared application suite tests
the integration between packages. Workspace installation does not enforce import
isolation, so wheel-isolation and architecture tests also verify the boundaries.
The package runner changes directories before invoking pytest, so each project uses
its own configuration, synthetic helpers and coverage output. Source remains editable;
tests do not require rebuilding wheels. The final command collects all package and
application tests through root `pytest.ini`.

## Build for deployment

```bash
uv run python scripts/release/build_sdk.py --output-dir .release/sdk
```

The build produces separate core, MongoDB adapter and API wheels. Deployment
installs these normally, without editable paths. The release workflow records
their versions and SHA-256 digests together and verifies them before installation.
No PyPI publication or PostgreSQL adapter is introduced.

To build one package directly:

```bash
uv build --package coyote-core
uv build --package coyote-mongo
uv build --package coyote-api
uv build --package coyote-pyclient
```

See [uv workspace behavior](https://docs.astral.sh/uv/concepts/projects/workspaces/)
and [release compatibility](compatibility.md).
