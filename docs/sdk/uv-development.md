# Editable development with uv

The repository is one uv workspace with three independently buildable distributions:

| Project | Distribution | Import | Version owner |
| --- | --- | --- | --- |
| `core` | `coyote-core` | `coyote` | `core/pyproject.toml` |
| Repository root | `coyote-server` | `coyote_api`, `coyote_mongo` | Root `pyproject.toml` |
| `clients/python` | `coyote-pyclient` | `coyote_pyclient` | Its `pyproject.toml` |

Workspace dependencies come from this checkout, not a public package index.
uv installs workspace members editable. One lockfile resolves their dependencies
together. The root `pyproject.toml` builds the server distribution from the separate
`api/src/` and `adapters/mongo/src/` trees and owns shared development dependency groups.
API and Mongo retain separate tests, coverage configurations and documentation;
they share the server version and deployment wheel.

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
uv run --package coyote-server uvicorn coyote_api.app.main:app \
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
uv run --package coyote-server pytest tests
uv run --package coyote-server pytest
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

The build produces core, combined server and independent Python client wheels.
The client supplies the image's administrative HTTP tools. Deployment installs
these normally, without editable paths. The release workflow records
their versions and SHA-256 digests together and verifies them before installation.
No PyPI publication or PostgreSQL adapter is introduced.

To build one package directly:

```bash
uv build --package coyote-core
uv build --package coyote-server
uv build --package coyote-pyclient
```

See [uv workspace behavior](https://docs.astral.sh/uv/concepts/projects/workspaces/)
and [release compatibility](compatibility.md).
