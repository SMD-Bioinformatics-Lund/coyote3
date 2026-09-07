# Dependency Advisory Policy

Upgrade vulnerable dependencies when a compatible fixed release exists. Do not use
blanket scanner suppression. Record an advisory-specific exception only with an
applicability assessment, mitigation, regression tests, and a review date.

## WeasyPrint presentational hints

Reviewed: 2026-09-07. Review again by 2026-10-07 and whenever WeasyPrint changes.

`PYSEC-2026-3412` (`CVE-2026-49452`, `GHSA-jhhc-3hcp-qhm5`) affects CSS construction
when HTML presentational hints are enabled. The dependency audit reports no fixed
release. Coyote3 explicitly calls `write_pdf(presentational_hints=False)` and uses
a resource fetcher restricted to embedded PNG/JPEG images. Network URLs, local files,
SVG resources, and oversized embedded images are rejected.

Regression tests in `tests/unit/reporting/test_release_regressions.py` verify the
disabled option and forbidden resource schemes. CI excludes this advisory ID only;
new advisories continue to fail the audit. Removing or relaxing either protection
requires removing the exception and reassessing the renderer before release.

This exception is not a clean raw scanner result or a general approval to render
arbitrary HTML. See the [upstream advisory](https://github.com/advisories/GHSA-jhhc-3hcp-qhm5).
