# Maintainer guide

Maintainers protect the stability of the clinical workflow, data contracts,
security boundaries, and release process.

## Change rules

| Rule | Required practice |
| --- | --- |
| Preserve behavior | Change an existing workflow only when the change is intentional, tested, and documented. |
| Use explicit contracts | Validate API and MongoDB boundaries with declared models. Do not depend on undocumented document shapes. |
| Keep one source of truth | Do not copy configurable values or fixed vocabularies into feature modules. |
| Test risk | Cover the success path, failure path, and permission boundary affected by the change. |
| Protect security | Never bypass authentication, authorization, CSRF, audit, or secret handling for development convenience. |
| Keep the branch healthy | Required CI checks must pass before merge. |

## Documentation diagrams

Maintain reviewed SVG diagrams directly. Preserve transparent backgrounds,
typography, accessible titles, relationship labels and the existing light/dark
palette. Inspect affected diagrams at their displayed size in both themes.

The sole logo blueprint is `scripts/branding/generate_logos.py`. Its source is
`frontend/public/logos/coyote4-logo.svg`. It preserves the animal, ring, Coyote
lettering and DNA. Version 4 retains its approved joined numeral. New version
numbers and package labels are outlined automatically using the bundled Lato Bold
Italic font; installed system fonts do not affect the result. Existing package
labels retain their approved outlines. New names require no code changes.

Install the generator's tooling dependencies if needed:

```bash
uv pip install --python .venv/bin/python -r scripts/branding/requirements.txt
```

Export SVGs to an ignored review directory before replacing maintained files:

```bash
# Application logo; omitting --version also selects 4.
.venv/bin/python scripts/branding/generate_logos.py --version 4 --output-dir .cache/brand-review
.venv/bin/python scripts/branding/generate_logos.py --version 5 --output-dir .cache/brand-review

# Existing or new package names use the same blueprint.
.venv/bin/python scripts/branding/generate_logos.py --name hop --output-dir .cache/brand-review
.venv/bin/python scripts/branding/generate_logos.py --name Orion --output-dir .cache/brand-review

# Separate print edition; the color asset is preserved.
.venv/bin/python scripts/branding/generate_logos.py --name hop --mono --output-dir .cache/brand-review
.venv/bin/python scripts/branding/generate_logos.py --mono --output-dir .cache/brand-review
```

Single-logo exports use filenames such as `coyote4-logo.svg`, `coyote5-logo.svg`,
`coyote-hop-logo.svg` and `coyote-hop-logo-bw.svg`. New labels preserve supplied
capitalization; registered names such as `hop` use the approved HOP lettering.
Major versions must be positive integers. Unsupported font characters produce an
error rather than substituted glyphs. Output SVGs contain paths, with no external
font dependency. Monochrome assets use black ink and white DNA on a transparent
background and are intended for printing on white.

`--all` exports the registered application, package and emblem assets into their
repository-relative locations under the output directory. The color export also
refreshes the bundled unavailable-page logo. This option replaces the previous
implicit bulk export. Add `--raster` for PNG output; with `--all`, it also produces
the current email PNG and browser ICOs. Raster export needs CairoSVG and Pillow.

After visual review, `--write --all` refreshes the registered assets, or
`--write --name hop` updates only the registered HOP logo. Use `--output-dir` for
new names and future application versions; integrating those into an application
is a separate deliberate change. Black-and-white files always have a `-bw` suffix.
The bundled font retains its SIL Open Font License in `scripts/branding/fonts/OFL.txt`.
Do not introduce additional artwork generators or logo-specific test suites.

## Pull request sequence

1. Define or update the domain behavior.
2. Update application services and persistence contracts.
3. Expose the behavior through the HTTP interface when required.
4. Update the frontend through shared API and UI components.
5. Add focused tests at each changed boundary.
6. Update the authoritative documentation.
7. Run the affected quality checks.

The [developer guide](../development/developer-guide.md)
explains where each responsibility belongs.

## Review checklist

Use the PR's affected modules to select [review criteria](contributing.md#module-update-checklist).
Confirm the stated behavior, actual validation results and any upgrade requirements.
Require appropriate clinical, security or operations review when those areas change.

| Area | Review question |
| --- | --- |
| Correctness | Does the implementation satisfy the stated behavior for positive and negative cases? |
| Clinical state | Can saved classifications, filters, comments, and reports still be reconstructed? |
| Access | Are route permissions, target-resource scope, and delegated administration enforced? |
| Persistence | Do repositories and Pydantic contracts own database access and validation? |
| Failure handling | Does failure leave the sample or resource in a valid state and create the required audit evidence? |
| Performance | Are indexes, pagination, caching, and query cardinality appropriate for production data? |
| Tests | Do tests prove behavior rather than internal implementation details? |
| Documentation | Is the current behavior described without release-note language? |

## Local verification

```bash
PYTHONPATH=. ruff check core api adapters services tests scripts
PYTHONPATH=. pytest -q
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/quality/run_family_coverage_gates.sh
npm --prefix frontend run lint
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm run docs:lint
.venv/bin/python -m mkdocs build --strict
```

Run affected Playwright suites for user-facing changes. Run disposable
full-stack validation for changes to ingest, deployment, authentication,
background tasks, or reporting.

## Releases

Follow the [release workflow](releasing.md): focused PRs into `dev`, a reviewed
release PR into `master`, then the immutable version tag and GitHub release.
Record full release validation separately from the inexpensive CI smoke checks.
