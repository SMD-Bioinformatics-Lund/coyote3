# Testing and Quality Gates

Coyote3 does not yet have a complete automated test suite and strict CI quality gates across all modules. This chapter is a placeholder to make that explicit and to define the direction for upcoming work.

For now, testing guidance is **coming soon**. Current validation is primarily manual and should focus on the highest-risk paths: permission enforcement, sample access boundaries, interpretation state updates, report save/retrieval behavior, and admin configuration mutations.

The intended next stage is to formalize layered coverage for unit behavior, route behavior, and workflow-critical integration behavior. Once that structure is in place, this chapter should be expanded with concrete gate requirements and execution commands that match the repository's actual test implementation.

## Production report format

This workflow belongs to the Flask production chain on `master`. It does not use
the API/version 4 application, its contracts, or its test suite.

`coyote/util/report/report_documents.py` builds JSON metadata and conditional
sections directly from the prepared DNA/RNA findings and reporting configuration.
It retains the production section conditions, numeric expressions, annotation
selection, and display filters. Source analysis HTML and formatted comments are
normalized for native Markdown fields; no report HTML is parsed into sections.
The package's sanitizer removes anchors, so narrative link destinations are kept
as visible text beside their labels.

`coyote/util/report/shared_renderer.py` validates JSON through `ReportLoader` and
passes it to `ReportRenderer`. The installed package owns all document templates,
styles, metadata layout, and HTML rendering. There are no post-render substitutions
or template overrides. JSON supplies `report.author_label` as
"Rapport genererad av"; the package renders the production author caption directly.
The host preview places that HTML in a sandboxed iframe.
Application controls, encrypted panel exports, and the finalization confirmation
belong to the surrounding Flask page. Save mode returns standalone report HTML
to the existing file/metadata/snapshot persistence workflow.

Install the production requirements in an isolated Python 3.12 environment, then run:

```bash
python -m pip check
```

Compare old and shared report content using synthetic samples across supported
DNA assay groups, paired samples, indel boundaries, annotations, RNA exclusions
and sorting, QC, empty reports, and permission-dependent preview controls.
Validate report preview, confirmation, and save/retrieval on a reviewed synthetic
installation before release. The JSON inputs can be inspected independently of
the HTML renderer.

The package is pinned to `smd-reports==0.4.1` without the optional PDF extra.
Its required Pydantic, text, font, and image dependencies replace conflicting
production pins in both dependency manifests. Unused Flask-WeasyPrint, WeasyPrint,
cssselect2, and pydyf dependencies are removed. Coyote3 exposes no PDF action.
The existing route paths, permissions, report collections, and snapshot contracts
remain unchanged; RNA retains the HTML-save workflow from `master`.

### Update and recovery record

- Owner: production report utility and DNA/RNA report workflows.
- Version: application release identity remains in `coyote/__version__.py`;
  template identity comes from the installed package. No extra version counters.
- Changelog: record presentation and required dependency changes under Unreleased.
- Clinical/security review: preserve existing clinical expressions, escaping,
  report permissions, encrypted gene-list interactions, and persistence ordering.
- Verification: compare report content and inspect synthetic HTML output after
  every template-package update. Check long narratives, images, pagination,
  keyboard actions, and wide/narrow browser layouts.
- Deployment/recovery: install from the reviewed production requirements. No data
  migration or historical-artifact rewrite is needed. To recover, restore the
  previous production code and its matching dependency environment together;
  retain all generated report files and database records.
- Remaining acceptance: authenticated report save/retrieval against a reviewed
  synthetic deployment. Docker validation is excluded from this task.
