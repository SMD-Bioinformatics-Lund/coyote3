# Versions and release compatibility

Coyote3 tracks application, package and report-template releases separately.
This page identifies their owners and explains which versions change together.

## Python client 1.0 authentication

Use `CoyoteClient.login()` or `AsyncCoyoteClient.login()` for password sessions,
and their `login_with_token()` methods for existing server sessions. Authentication
is owned by these clients. They validate response contracts, require the
configured session cookie, preserve deployment prefixes, and send bearer tokens
through their owned transports. Explicit CLI token export uses `client.session_token`;
normal output and user metadata exclude this credential.

## Version identities

There are **five release version numbers**: one application version, two Python
package versions, and two modern report-template versions.

| Component | Current version | Authoritative source | What it identifies |
| --- | --- | --- | --- |
| Application, including the UI | `4.0.0` | `application_version` in `release.toml` | Tested frontend, API, worker and selected SDK combination. The UI has no independent release counter. |
| Core SDK/server package | `1.0.0` | `[project].version` in `pyproject.toml` | Installable `coyote3` core, bundled API modules and report assets. Changed wheel content requires a new published package version. |
| Python client SDK | `1.0.0` | `[project].version` in `clients/python/pyproject.toml` | Independent HTTP-only `coyote3-client` package, imported as `coyote3_client`. |
| Modern DNA report template | `1.0.0` | `[dna].version` in `src/coyote3/templates/reporting/modern/manifest.toml` | DNA presentation release printed above the page number in the PDF footer. |
| Modern RNA report template | `1.0.0` | `[rna].version` in the same template manifest | RNA presentation release printed above the page number in the PDF footer. |

Matching version numbers do not couple release cycles. DNA and RNA can advance
independently; changes to shared report HTML, CSS or fonts require both template
versions to advance. Published artifacts must never be replaced with different
content under the same version.

`package.json` and `frontend/package.json` mirror the application version through
`npm run sync:version`; they are not additional version authorities. The
`sdk_version` in `release.toml` selects an existing core SDK version for the
application, rather than introducing a sixth release counter. There is no separate
`APPLICATION_SDK_VERSION` counter.

### Compatibility markers and record revisions

These values serve other purposes and are not additional software/template releases:

| Identifier | Authoritative source | Meaning |
| --- | --- | --- |
| HTTP API major | `http_api_major` in `release.toml`, matching `/api/v1` | HTTP compatibility generation, currently `1`. It is independent of application `4.0.0` and package `1.0.0`. |
| Center configuration format | `center_configuration_format` in `release.toml` | Supported staged configuration manifest format, currently `1`. |
| Template content hash | Packaged template sources and the selected analyte's version | Exact presentation identity checked against the approved template profile; the hash is separate from the readable footer version. |
| Clinical configuration/data revisions | Published resources and migration contracts | Assay configurations, query policies, reporting rules and stored-data compatibility. |
| Patient report number | The sample's report history | Identifies successive reports for a sample; it does not set the template version. |
| Pipeline/reference-data versions | Ingested sample metadata and installed reference releases | Records the analysis pipeline and sources such as VEP used for interpretation. |

The remote client follows the supported HTTP API generation rather than importing
or pinning the server's internal Python interface. See
[HTTP API compatibility](../api/versioning-and-compatibility.md) for that contract.

## Decide when to release

Use `MAJOR.MINOR.PATCH` for the SDK's documented supported Python interface:

- Patch: compatible corrections.
- Minor: compatible capabilities or deprecations.
- Major: incompatible imports, arguments, result meanings, errors or supported behavior.

The supported interface includes the documented application and remote-client
operations, not every internal service or repository. The application release
also communicates compatibility: compatible fixes use patch releases, compatible
features use minor releases, and incompatible supported application changes use
major releases. Clinical changes still require their established review and
regression validation regardless of version classification.

Ordinary working-tree edits do not require new release numbers. Released artifacts
are immutable. Use Python development or candidate versions such as `1.1.0.dev1`
and `1.1.0rc1` for unreleased SDK builds. Environment image labels such as `-dev`
are deployment labels and are not Python package versions.

A frontend-only or deployment-only fix can release a new application using the
same SDK. Changes to API code bundled in the wheel require a new SDK/server package
version. An SDK-only release need not release the application; when adopting it,
select its version and release a new tested application combination. An SDK breaking
change does not require `/api/v2` if the API preserves its HTTP contract.

Report layout changes follow the [template release process](../development/report-templates.md#template-bundle-releases).
Update the affected DNA/RNA manifest versions when releasing those templates.
Because the assets ship inside the core/server wheel, publishing changed templates
also requires a new SDK/server package version. Ordinary uncommitted edits do not
require version increments before release.

## Build and record an application release

1. Set the SDK source version in `pyproject.toml` if releasing library changes.
2. Set `application_version` and the exact `sdk_version` in `release.toml` when
   releasing the application. Run `npm run sync:version` to update application
   package metadata. Review npm lockfile metadata if the application version changes.
3. Run the applicable test and quality gates from a clean reviewed checkout.
   Build the SDK, install that exact wheel, and test the installed package:

   ```bash
   .venv/bin/python scripts/release/build_sdk.py --output-dir .release/sdk
   .venv/bin/python -m pip install --no-deps --force-reinstall \
     .release/sdk/coyote3-1.0.0-py3-none-any.whl
   PYTHONPATH=. .venv/bin/pytest -q tests/unit tests/api tests/integration
   .venv/bin/python scripts/release/check_release.py --production \
     --wheel .release/sdk/coyote3-1.0.0-py3-none-any.whl \
     --output .release/sdk/release-record.json
   export GIT_COMMIT="$(git rev-parse HEAD)"
   ```

   The filename above illustrates the current version; select the wheel for the
   actual release. The check verifies its metadata and digest and rejects the
   independent HTTP client and retired modules in the library artifact. The builder stages sources
   into a fresh directory so old local build outputs cannot enter the wheel.
   The check also compares actual HTTP route generations and supported center
   configuration formats with `release.toml`. Unsupported staged manifest formats
   are rejected when loading center configuration. The JSON records software versions, contract
   generations, source commit, dirty-checkout status and the wheel SHA-256.
4. Retain the tested wheel and record as CI/release artifacts. Production record
   generation rejects a dirty checkout. The production Dockerfile verifies the
   wheel checksum, metadata, application selection and exact source commit before
   installation. It retains both files under `/opt/coyote3-sdk/` in the image.
   Retain deployment
   image digests and the selected center manifest alongside it.
5. Tag SDK and application releases separately, for example `sdk-v1.0.0` and
   `app-v4.0.0`. Publishing to a public package index is not required.

Normal installations use the `coyote3_source_api` Docker target. It builds the
application wheel from the checkout in a separate Docker build stage and installs
it into the runtime image. The installer requires no host SDK build or release
artifact directory. API and workers use the same resulting image.

Release CI can select the `coyote3_api` target directly or add
`-f deploy/compose/docker-compose.release.yml` after the base Compose file. This
optional path reads the named `sdk_artifact` context from `.release/sdk`.
To use downloaded CI artifacts elsewhere, export
`COYOTE3_SDK_ARTIFACT_DIR` as an absolute directory containing the wheel and
`release-record.json`. Build API and workers from those retained artifacts using
the same source checkout and `GIT_COMMIT`; do not rebuild the wheel on the deployment
host on this verified-artifact path. The CI container build consumes the wheel
produced and tested by its Python job.

For a disposable validation of uncommitted work, omit `--production` when creating
the record and explicitly pass Docker build argument
`COYOTE3_ARTIFACT_MODE=development`. Such images carry a development artifact label
and cannot satisfy production artifact verification. The development Compose
overlay uses `docker/Dockerfile.dev` and needs no wheel artifact. After testing an
installed wheel locally, restore editable development with
`.venv/bin/python -m pip install --no-deps -e .`.

The normal application check requires the selected SDK to match the library
built from that checkout. Rebuild API and worker images together. API and worker
startup rejects an installed SDK version different from the application's selected
version. Older released
application combinations remain available from their immutable tags and artifacts.
For an SDK-only release ahead of application adoption, use
`python scripts/release/check_release.py --sdk-only`. That does not update or
approve the application's SDK selection.

Integrated application tests use the SDK built from the same checkout. When SDK
source versions advance, the application development manifest must select that
version for those tests. Update the planned application version before releasing
the new combination. Selecting a dependency for development does not publish an
application release; SDK and application tags remain separate. Previously released
applications keep their original manifest and SDK artifacts.

The renderer's existing report receipt `software_version` identifies the SDK
containing the rendering logic. Application/deployment identity is retained in
the application release record; existing clinical snapshot formats are unchanged.

## Python import migration

The supported local operation imports now use `coyote3.application.operations`.
The host factory is `api.app.application_factory`, and HTTP dependency providers
are in `api.app.deps.application`. The old `application.sdk`, `app.sdk` and
`deps.sdk` module paths have been removed without compatibility aliases.

See [HTTP versioning](../api/versioning-and-compatibility.md) for endpoint
compatibility and [application upgrades](../deployment/application-upgrades.md)
for deployment and configuration migration requirements.
