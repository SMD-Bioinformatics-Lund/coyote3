# Development

Atlas uses a standard `src/coyote_atlas` package with package-owned `tests/`,
documentation, license notices and coverage settings. Editable installation
makes Python source changes available without rebuilding a wheel:

```bash
uv pip install -e 'services/atlas[test,api]'
```

From this package directory, using the activated development environment:

```bash
python -m pytest -m smoke -q
python -m pytest tests/unit tests/smoke -q
python -m pytest --cov=coyote_atlas --cov-report=term-missing
```

The API suite uses a synthetic FastAPI host and mocked persistence. It requires
the optional API dependencies and explicit synthetic host configuration; it
never needs a running MongoDB. Package tests do not import another package's
test helpers. Coverage includes all Atlas production source and uses the
package's own floor.

Build from this directory or a copied standalone source archive:

```bash
python -m pip install build
python -m build
```

The build needs no repository-parent files. Dependencies must be available from
the configured package source. Wheels include the checked resources, diagrams
and source notices; source distributions additionally include package docs and
tests. Validate a built wheel's bundle from outside the checkout before release.

Reference updates require reviewed source evidence, a new dataset identity and
updated manifest counts and hashes. Preserve upstream notices and core clinical
contracts. Do not edit installed package resources or fetch new references during
application startup. Package upgrades alone do not replace stored references.

Maintainer workflows can use `coyote_atlas.authoring.draft_bundle(output, version)`
as a context manager. It copies packaged resources to a new directory, lets the
caller update reviewed data there, then regenerates and validates the inventory.
An exception leaves an unapproved review copy. This operation neither publishes
a package nor installs database records. Repository VEP maintenance commands use
this workflow with explicit `--output-bundle` and `--bundle-version` arguments.
