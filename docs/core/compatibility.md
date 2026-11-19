# Versions and release compatibility

Each package owns its version. Application releases select an exact tested
combination; package installation and public-index publication are separate tasks.

## Version identities

| Identity | Authoritative owner |
| --- | --- |
| Core version | `core/pyproject.toml`, distribution `coyote-core` |
| Server version, shared by API and MongoDB adapter | Root `pyproject.toml`, distribution `coyote-server` |
| HTTP client version | `pyproject.toml` in the independent pyClient repository |
| Ingestion service version | `services/relay/pyproject.toml` |
| Reference service version | `pyproject.toml` at the Atlas revision pinned in `uv.lock` |
| Demo package version | `services/demo/pyproject.toml` |
| Application selection | `release.toml`: application and five selected Python distribution versions |
| HTTP generation | Declared `/api/vN` routes, checked against `http_api_major` |
| Center configuration format | Core loader, checked against `center_configuration_format` |
| Report templates | Installed `smd-reports` version |

`sdk_version` selects core and its reusable contracts; `server_version` selects the API and adapter together;
`relay_version` selects the ingestion service and submission commands;
`atlas_version` selects reference resources and workflows; `demo_version` selects
the optional demonstration package.
Each distribution version is independent of `application_version`.
Declared package dependencies must agree with the selected combination. The initial
Coyote4 application selects core `4.0.0` and version `1.0.0` for the server,
Relay, Atlas and Demo. The independent HTTP client has its own version
and compatibility checks; it is not part of the application artifact set.

Atlas is an external Git dependency. Its full reviewed commit belongs to `[tool.uv.sources]` in the root `pyproject.toml` and the resolved
`uv.lock`. Adopting an external change requires updating those pins and selecting
the corresponding version in `release.toml`. Build provenance retains the Git
source and artifact checksum. No floating branch is used for deployment.
Core models and feature modules share one version. Optional `reporting` and
`alignment` extras select third-party dependencies and introduce no additional
Coyote distributions; the server explicitly requires both.

`npm run sync:version` updates frontend metadata and generates the API's packaged
`config/application_release.toml` from the application selection. It supplies the
application label to the installed host without requiring the repository at runtime.
Release validation rejects a stale generated label. OpenAPI identifies the server
package version; UI and deployment environment labels identify the application.
As with other packaged content, changing the bundled label requires a new server
artifact version after its first release; published wheels must remain immutable.

The HTTP client follows the public HTTP contract and does not pin or import the
server's internal packages. See [HTTP compatibility](../api/versioning-and-compatibility.md).

## Decide when to release

Use semantic versions for each package's documented supported interface:
compatible corrections are patches, compatible capabilities are minor releases,
and incompatible changes are major releases. Ordinary uncommitted edits do not
require release increments. Released artifacts are immutable.

Change only affected package versions, then update the application's exact
dependency selection when adopting those versions. A MongoDB-only implementation
change requires a server release but does not require a new core version. A breaking core change does not
necessarily require a new HTTP generation if the host preserves its wire contract.

Environment suffixes such as `-dev` label application images, not Python package
versions. Clinical changes retain their established review and validation needs.

## Build and record an application release

1. Update affected package metadata and dependency pins.
2. Select the tested versions in `release.toml`; run `npm run sync:version` when
   the application version changes.
3. Build, install and test the exact wheels:

   ```bash
   .venv/bin/python scripts/release/build_sdk.py --output-dir .release/sdk
   .venv/bin/python -m pip install --no-deps --force-reinstall .release/sdk/*.whl
   PYTHONPATH=. .venv/bin/pytest -q
   .venv/bin/python -m scripts.release.check_release --production \
     --wheel-dir .release/sdk --output .release/sdk/release-record.json
   export GIT_COMMIT="$(git rev-parse HEAD)"
   ```

4. Retain all five wheels and the record together. Production records require a
   clean checkout. Verification rejects missing, modified, extra or wrongly
   versioned wheels and mismatched source commits.
5. Retain image digests and the reviewed center configuration alongside the record.
   Publishing to PyPI is not part of this workflow.

Use an output directory containing only the selected five release wheels.
Core-only validation can use `check_release.py --sdk-only`; it does not approve
a complete application release.

Normal installations use the `coyote4_source_api` Docker target, which builds
separate wheels during deployment. API and workers share the resulting image.
This image installs four distributions (core, server, Relay and Atlas);
the separate demo target adds Demo.

Release CI can use `coyote4_api` or the release Compose overlay. Its
`sdk_artifact` build context points to the retained artifact directory.
`COYOTE4_SDK_ARTIFACT_DIR` can select an absolute downloaded artifact directory.
This path installs the tested wheels without rebuilding them.

For disposable validation of uncommitted work, omit `--production` and explicitly
select `COYOTE4_ARTIFACT_MODE=development`. Such a record cannot pass production
verification. No Docker build or deployment is implied by generating a record.

Restore editable development after testing installed wheels:

```bash
uv sync --all-packages --group test --group dev --group docs
```

Report receipts retain the core rendering-code version; application provenance
belongs to the release record. Clinical snapshot formats do not change with
this packaging split.

## Python import migration

Core operations remain under `coyote.application.operations`; API imports now use
`coyote_api`. MongoDB implementations now import from `coyote_mongo`.
The old API-owned MongoDB paths are removed without forwarding modules.

See [package boundaries](package-boundaries.md) and
[application upgrades](../deployment/application-upgrades.md).
