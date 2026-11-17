# Editable development with uv

The repository is one uv workspace with four editable distributions and the external Relay dependency:

| Project | Distribution | Import | Version owner |
| --- | --- | --- | --- |
| `core` | `coyote-core` | `coyote` | `core/pyproject.toml` |
| Repository root | `coyote-server` | `coyote_api`, `coyote_mongo` | Root `pyproject.toml` |
| External Relay repository | `coyote-relay` | `coyote_relay` | Its `pyproject.toml` |
| `services/atlas` | `coyote-atlas` | `coyote_atlas` | Its `pyproject.toml` |
| `services/demo` | `coyote-demo` | `coyote_demo` | Its `pyproject.toml` |

uv installs workspace members editable. Relay comes from the
exact Git commit in `[tool.uv.sources]`; it is not a workspace member. One lockfile
resolves their dependencies together. The root `pyproject.toml` builds the server distribution from the separate
`api/src/` and `adapters/mongo/src/` trees and owns shared development dependency groups.
API and Mongo retain separate tests, coverage configurations and documentation;
they share the server version and deployment wheel.

## Set up once

Use Python 3.14.7 for the application environment. Install uv using the
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root:

```bash
uv sync --frozen --all-packages --group test --group dev --group docs
```

This creates or synchronizes `.venv`. It may remove packages installed manually
that are outside the selected workspace dependencies. Keep optional load tools
in their documented separate environment.

## Edit and run

For the fastest development loop, run the API and workers natively in this editable
workspace and use the local watcher below. Docker backend services use explicit
restarts or rebuilds; their source mounts do not reload running Python processes.

```bash
./install.sh watch --env-file .coyote4_dev_env -- \
  .venv/bin/python -m uvicorn coyote_api.app.main:app --host 127.0.0.1 --port 8001
```

Supply the existing environment configuration before starting the API. This
command does not launch MongoDB, Redis or workers.
Demo remains disabled in this workspace unless explicitly enabled against its
isolated targets; follow the [demo guide](../deployment/demo-installation.md) to
run it, including its guarded worker entry point.

The environment file must select `ENV_NAME=dev` or `development` and use
host-reachable endpoints. The installer watches all editable backend package
sources, including core, API, Mongo, Atlas and Demo sources that are
present. Python and packaged configuration/template changes restart the process.
It uses polling for WSL-mounted filesystems and debounces consecutive edits.
Do not combine it with Uvicorn's separate `--reload` supervisor.

Start an ingestion worker with the same reviewed host configuration:

```bash
./install.sh watch --env-file .coyote4_dev_env -- \
  .venv/bin/coyote-relay-worker --loglevel INFO
```

The same wrapper supports maintenance workers, beat and other long-running backend
commands. Reload sends SIGTERM, waits up to 30 seconds for shutdown, then terminates
remaining child processes before restarting. Use it only with development jobs.
Submission commands use the base package and do not need database credentials.
For joint Relay development, install your external Relay checkout editable into
this virtual environment with `uv pip install --python .venv/bin/python -e PATH`.
Add its `src` directory with `--directory PATH` before `--` in the watch command.
The next normal `uv sync --frozen` restores the selected Git revision. This local
override does not change the application lockfile or Docker images.

Frontend development remains separate:

```bash
npm --prefix frontend run dev
```

Vite refreshes React components, CSS and imported assets. For Windows editors writing
through WSL mounts, set `CHOKIDAR_USEPOLLING=true` in that terminal.

Docker development uses source bind mounts and explicit backend lifecycle commands:

```bash
./install.sh compose --env-file .coyote4_dev_env --environment dev up -d --build
```

Both modern and legacy development definitions mount the backend package sources.
A saved file is visible inside the container immediately, but an already running
Python process keeps its imported code until restarted. API, ingestion and
maintenance workers, beat and monitor run without backend watchers. Vite continues
to update frontend components and CSS automatically.

After editing shared backend sources, restart the affected services explicitly:

```bash
./install.sh compose --env-file .coyote4_dev_env --environment dev \
  restart api worker maintenance-worker beat monitor
```

Select only the affected services when the change is isolated. Run worker restarts
after development jobs have finished. A source-only change to a mounted package
does not require an image rebuild. Changes to dependencies, versions, entry points,
the installed external Relay revision or Docker image contents require rebuilding
and recreating services with `up -d --build`. The Relay Git installation is not a
source bind mount. Add `--legacy` for the older-host definitions.

An explicit `--compose-file` selection replaces profile defaults; include the development
definition when overriding the file list. Production, staging and test profiles
also run without source reload watchers.

For native development, run `uv sync` again after changing dependencies, versions
or entry points. Environment files, center configuration and Compose definitions
require an explicit service restart or recreation. Frontend source and CSS edits
use Vite hot updates in both development modes.

## Run tests

Prepare the pinned Relay wheel with `./install.sh dependencies` before running
installed-distribution integration tests. Those tests consume the prepared artifact
and perform no Git fetches.

```bash
scripts/quality/run_package_tests.sh core
scripts/quality/run_package_tests.sh mongo
scripts/quality/run_package_tests.sh api
scripts/quality/run_package_tests.sh atlas
scripts/quality/run_package_tests.sh demo
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
tests do not require rebuilding wheels. The final command collects all local package and
application tests through root `pytest.ini`. Relay-owned tests run in its repository;
the application retains installed-artifact checks.

## Build for deployment

```bash
uv run python scripts/release/build_sdk.py --output-dir .release/sdk
```

The build produces four local wheels and includes the Relay wheel built from its
pinned Git revision. The installer prepares that wheel on the host in
`.release/relay` before Compose builds, including `up --build`. Direct Docker
builds require `./install.sh dependencies` first. Git and pip must be available on
the host. Modern and legacy images receive only the wheel and its source/checksum
record; they do not need GitHub credentials. Normal application images install all
except Demo; dedicated demo images add it explicitly. The application owns its
administrative HTTP tools, Relay supplies ingestion workers and submission commands,
and Atlas supplies reference bundles. Production deployment installs wheels without
editable paths. The release workflow records
their versions and SHA-256 digests together and verifies them before installation.

To build one package directly:

```bash
uv build --package coyote-core
uv build --package coyote-server
uv build --package coyote-atlas
uv build --package coyote-demo
```

See [uv workspace behavior](https://docs.astral.sh/uv/concepts/projects/workspaces/)
and [release compatibility](compatibility.md).
