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

Runtime pins include Brotli 1.2.1, dnspython 2.9.0, filelock 4.2.1, and PyMongo
4.18.3. Keep `requirements.txt` synchronized with `pyproject.toml` when changing
them. Audit the declared dependencies as well as the installed environment:

```bash
.venv/bin/pip-audit -r requirements.txt
.venv/bin/pip-audit -r requirements-dev.txt
.venv/bin/pip-audit
npm audit
npm --prefix frontend audit
```

Existing virtual environments can retain vulnerable transitive dependencies even
when a fresh resolution is clean. Rebuild or update those environments and audit
them again; a clean manifest audit does not validate running container images.
GitHub alerts track the default branch, so fixes on a release branch do not close
those alerts until incorporated into the default branch and rescanned.

The documentation tooling overrides `re2js` to 2.8.7 because markdownlint 0.42.0
selects a vulnerable release. This addresses
[GHSA-gg6h-894w-4m9c](https://github.com/advisories/GHSA-gg6h-894w-4m9c)
without downgrading markdownlint. Reassess the override when markdownlint updates.

## WeasyPrint presentational hints

Reviewed: 2026-09-09. Reassess whenever WeasyPrint changes.

`PYSEC-2026-3412` (`CVE-2026-49452`, `GHSA-jhhc-3hcp-qhm5`) affects CSS construction
when HTML presentational hints are enabled in affected releases. Coyote3 pins
WeasyPrint 70.0; the dependency audit passes without an advisory exception.
Coyote3 explicitly calls `write_pdf(presentational_hints=False)` and uses
a resource fetcher restricted to embedded PNG/JPEG images, validated self-contained
SVG logos, and WOFF2 fonts. SVG scripts, external references and nested images are rejected.
Network URLs, local files and oversized embedded images are rejected.

Regression tests in `tests/unit/reporting/test_release_regressions.py` verify the
disabled option and forbidden resource schemes. CI does not suppress this advisory.
Removing or relaxing either protection requires reassessing the renderer before release.

Passing dependency checks is not approval to render arbitrary HTML. PDF layout
must also be reviewed before clinical deployment after renderer upgrades. See the
[upstream advisory](https://github.com/advisories/GHSA-jhhc-3hcp-qhm5).
