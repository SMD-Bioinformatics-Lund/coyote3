# Development

Relay lives in `services/relay/` in the application workspace. Core, server and
Relay changes can share one branch, PR and dependency resolution. Python imports,
command names and installed entry points do not depend on this source location.

From the application root:

```bash
uv sync --frozen --all-packages --group test
bash scripts/quality/run_package_tests.sh relay
```

For submission-only development, install the matching reviewed Core artifact,
then install this package editable with `python -m pip install -e '.[test]'`
from its directory. Base submission needs neither MongoDB nor Redis. API and worker
tests need the selected server dependencies but use synthetic repositories and
mocked services. They do not connect to an existing deployment.

## Dependencies

`pyproject.toml` owns Relay's requirements. The root `uv.lock` resolves the
application and its test tools. The package's `requirements.txt` and
`requirements-dev.txt` are pip entry points to that metadata, not separate locks.
Core is selected by version; use the application's reviewed wheel set while these
packages are not published to PyPI. Do not install unrelated same-named packages.

Native development watches Relay with the other workspace sources. Docker backend
processes require an explicit restart or rebuild. See the application
[development guide](../../../docs/core/uv-development.md).

## Tests and releases

- `tests/unit`: receipts, transport failures, credentials, validation and artifacts.
- `tests/smoke`: fast command and manifest checks without services.
- `tests/api`: routes, authentication, permissions, scopes and uploads.
- `tests/worker`: core workflow composition, task execution and recovery.

Root CI runs the smoke suite. Run the full package suite for Relay changes; run
composed application checks when host behavior changes. Core ingestion regressions
belong to Core. Retain package-owned tests and the existing coverage gate.

Relay builds as its own wheel with the other application artifacts. Work through
`dev`; the application release PR targets `master`. Update Relay metadata,
changelog and `release.toml` together when releasing a changed Relay artifact.
Use `vMAJOR.MINOR.PATCH` for changelog headings, tags and release titles. Follow the
application [release procedure](../../../docs/project/releasing.md).
