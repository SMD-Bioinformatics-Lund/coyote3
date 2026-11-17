# Develop the HTTP client

Run the following commands from the client project directory. They work in a
standalone checkout and in `clients/python` inside the application workspace.
Python 3.12 or later and [uv](https://docs.astral.sh/uv/getting-started/installation/)
are required for these examples.

## Isolated editable installation

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[test]"
.venv/bin/python -m pytest -q tests/smoke
```

This environment installs only the client, HTTPX, Pydantic and test dependencies.
The API, core and database adapter are not required. Source edits take effect in
new processes without rebuilding a wheel. Reinstall after changing dependencies,
package metadata or entry points.

For coordinated application work, the parent uv workspace can instead install the
client editable alongside the other packages. Application contract tests remain
owned by that workspace; they are not required to run this client's unit tests.

## Tests and coverage

`tests/unit` checks synchronous and asynchronous authentication, resource access,
validation and transport failures. `tests/smoke` covers authenticated report-preview
transport. Both use HTTPX mock transports and synthetic responses; no running
server, database or credentials are needed.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage includes the complete `coyote_pyclient` namespace and branches, with an
81% baseline floor. Outputs are `.coverage` and `coverage/coverage.xml`; add
`--cov-report=html` for `coverage/html/`. Smoke checks do not enforce full-suite coverage.

Keep synchronous and asynchronous behavior aligned for authentication, timeouts,
pagination, mutations and error handling. Preserve response validation and additive
server fields. New endpoints need synthetic success, permission and failure cases.

## Build

```bash
uv build --package coyote-pyclient
```

This produces a wheel and source distribution in `dist/`. The package has no
workspace dependency or parent-directory build hook. Test retained artifacts in
an isolated environment before release; see [releasing](releasing.md).

The package's `.github/workflows/quality.yml` runs smoke checks and a wheel build
when this directory becomes a repository root. While nested in the application,
the application workflow runs its client smoke suite.
