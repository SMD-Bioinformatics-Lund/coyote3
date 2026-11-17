# Release the Python client

The distribution `coyote-pyclient` and namespace `coyote_pyclient` have their own
version. Client 1.x targets the Coyote4 `/api/v1` HTTP contract. Application version
numbers do not determine the client version, and Coyote3 Flask routes are unsupported.

## Versioning

Use semantic versioning in `pyproject.toml`:

- Patch: compatible bug fixes.
- Minor: compatible new client functionality.
- Major: incompatible public interfaces or supported HTTP contracts.

Record user-visible changes in `CHANGELOG.md`. Keep the README version badges
consistent with the selected package version.

## Verification and release

1. Run all package tests with coverage using [development](development.md).
2. Run the application's client/API contract tests against the candidate server.
   Mock transport tests alone do not establish server compatibility.
3. Build the source distribution and wheel with `uv build --package coyote-pyclient`.
4. Install each artifact in a fresh environment with only its declared dependencies
   and test extras. Run the smoke suite and full client tests from outside the source
   checkout. Confirm that importing the client requires no core, server or database adapter.
5. Review a release PR from `dev` to `master`. After approval and merge, tag the
   release `vMAJOR.MINOR.PATCH` and retain the tested artifacts and release notes.

The smoke workflow does not publish to a package index. Package-index publication
requires a separately configured and approved release process.

## Repository extraction

Use this project directory as the new repository root, preserving `src`, `tests`,
`docs`, project metadata, build hook, license/notices and `.github` configuration.
Run the verification above from that checkout before changing application dependencies.

Until extraction, the application uses the editable workspace member. After the
repository exists, pin its reviewed Git commit in the application's uv sources and
lockfile, update build inputs, and rerun composed tests. Use an exact commit instead
of a floating `dev` branch. Remove the workspace copy only when those consumers use
the reviewed repository revision. Do not maintain two authoritative copies.
