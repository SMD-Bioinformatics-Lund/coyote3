# Interface Visual Reference

This page collects current Coyote3 interface screenshots used across training,
deployment validation, and product documentation. The images show the current
React application style: glass surfaces, bordered clinical tables, compact
badges, contextual navigation, and the public information pages.

> **Info: Sample-neutral screenshots**
>
>
> The screenshots are documentation fixtures. They are intended to explain the
> interface layout and should not contain real clinical identifiers.
>

## Login And Public Entry

The login page provides local and LDAP sign-in, a public catalog entry point,
and center-owned organization text from the configured contact metadata.

[![Login page](../assets/screenshots/login.png)](../assets/screenshots/login.png)

## Operational Dashboard

The dashboard summarizes sample throughput, review state, finding availability,
assay workload, and operational capacity using compact cards and shared plotting
components.

[![Operational dashboard](../assets/screenshots/dashboard.png)](../assets/screenshots/dashboard.png)

## Sample List

The sample list is the primary triage table. It separates live and reported
samples, shows profile and report badges, and uses short count badges for
available analysis domains.

[![Sample list](../assets/screenshots/samples.png)](../assets/screenshots/samples.png)

## Sample Overview

The sample overview presents case/control metadata, files and QC state,
biomarkers, selected gene panels, and the high-level report state for the
clinical case.

[![Sample overview](../assets/screenshots/samples_overview.png)](../assets/screenshots/samples_overview.png)

## Small Variant Review

The small-variant view combines active gene-panel context, tab-specific filters,
knowledgebase badges, compact evidence columns, and bulk review controls.

[![Small variant review](../assets/screenshots/samples_small_variants.png)](../assets/screenshots/samples_small_variants.png)

## CNV Review

The CNV view uses the same sample workspace conventions while presenting
copy-number calls, filter state, and action controls for structural dosage
events.

[![CNV review](../assets/screenshots/samples_cnvs.png)](../assets/screenshots/samples_cnvs.png)

## Report Preview

The report preview renders the current temporary clinical report context before
the reviewer saves a finalized report snapshot.

[![Report preview](../assets/screenshots/samples_report_preview.png)](../assets/screenshots/samples_report_preview.png)

## Assay Catalog

The assay catalog combines center-owned catalog metadata with configured ASP,
ASPC, and ISGL records.

[![Assay catalog](../assets/screenshots/assay_catalog.png)](../assets/screenshots/assay_catalog.png)

## Assay Catalog Matrix

The matrix shows gene coverage across assay sections, groups, assays, and
subpanels. The header hierarchy mirrors the clinical catalog grouping.

[![Assay catalog matrix](../assets/screenshots/assay_catalog_matrix.png)](../assets/screenshots/assay_catalog_matrix.png)

## Tiered Variant Search

The tiered variant search page supports targeted annotation lookup, assay-level
summary counts, and compact evidence text display.

[![Tiered variant search](../assets/screenshots/tiered_variant_search.png)](../assets/screenshots/tiered_variant_search.png)

## Administration Workspace

Administration pages use the same card and table system as clinical pages, with
typed forms for configuration and explicit permissions for mutation workflows.

[![Administration home](../assets/screenshots/admin.png)](../assets/screenshots/admin.png)

## Contact Page

The contact page is generated from center configuration and provides operational
support information without requiring an authenticated session.

[![Contact page](../assets/screenshots/contact.png)](../assets/screenshots/contact.png)
