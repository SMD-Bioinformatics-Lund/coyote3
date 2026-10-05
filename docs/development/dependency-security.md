# Dependency Advisory Policy

Upgrade vulnerable dependencies when a compatible fixed release exists. Do not use
blanket scanner suppression. Record an advisory-specific exception only with an
applicability assessment, mitigation, regression tests, and a review date.

## Python runtime and tooling

API and worker images use stable Python **3.14.7**, with the default GIL-enabled
interpreter. Runtime CI tests the same patch release. Shared scripts, documentation,
and security tooling also retain Python 3.12 compatibility. No prerelease Python
runtime or Rust toolchain is required by the supplied Dockerfiles.

Starlette, pyasn1, and idna are explicitly pinned to patched releases. FastAPI
0.141.1 uses nested router contexts; route contract and authorization tests inspect
them with `fastapi.routing.iter_route_contexts`, including schema-hidden routes.

## WeasyPrint presentational hints

Reviewed: 2026-09-09. Reassess whenever WeasyPrint changes.

`PYSEC-2026-3412` (`CVE-2026-49452`, `GHSA-jhhc-3hcp-qhm5`) affects CSS construction
when HTML presentational hints are enabled in affected releases. Coyote3 pins
WeasyPrint 70.0; the dependency audit passes without an advisory exception.
Coyote3 explicitly calls `write_pdf(presentational_hints=False)` and uses
a resource fetcher restricted to embedded PNG/JPEG images. Network URLs, local files,
SVG resources, and oversized embedded images are rejected.

Regression tests in `tests/unit/reporting/test_release_regressions.py` verify the
disabled option and forbidden resource schemes. CI does not suppress this advisory.
Removing or relaxing either protection requires reassessing the renderer before release.

Passing dependency checks is not approval to render arbitrary HTML. PDF layout
must also be reviewed before clinical deployment after renderer upgrades. See the
[upstream advisory](https://github.com/advisories/GHSA-jhhc-3hcp-qhm5).
