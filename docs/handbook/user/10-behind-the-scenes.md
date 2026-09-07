# Behind the Scenes for Users

This chapter explains internal behavior that affects what users see.

## Core collections used by user workflow

- `samples`: sample identity, filter state, report history.
- `variants`: SNV/indel events for DNA.
- `cnvs`: CNV events.
- `transloc`: translocation events.
- `annotation`: global class/text interpretations.
- `reported_variants`: immutable report-time variant snapshots.
- `assay_specific_panels`: panel gene coverage baseline.
- `asp_configs`: assay-specific behavior/filter/report config.
- `insilico_genelists`: user-selectable ISGL filters.

## Why variants can appear pre-tiered

Coyote3 does not only rely on current sample-local actions.

It queries historical `annotation` docs and picks latest matching class by identity and assay scope.

Identity match order:

1. protein (`HGVSp`)
2. coding (`HGVSc`)
3. genomic (`CHR:POS:REF/ALT`)

Scope rule:

- `solid`: assay + subpanel scoped class is preferred.
- other assays: assay scoped class is preferred.

## Annotation collection behavior

`annotation` stores two doc types in one collection:

- class docs (`class` present)
- text docs (`text` present)

When you classify a variant, Coyote3 inserts class doc (and in some bulk flows also text doc).

When you remove class, class docs are removed by variant identity and assay scope rules.

## Effective genes and why your list changes

Effective gene set is computed as:

- baseline from ASP covered genes
- combined with selected ISGL and ad-hoc genes

Then:

- normal assays: intersection with ASP baseline
- `tumwgs`/`wts`: direct use of selected filter genes

So modifying ISGL/ad-hoc settings changes what variants remain visible.

## How sample state changes over time

Live sample behavior is mutable:

- sample filters can be changed repeatedly
- comments can be added/hidden/unhidden
- global annotations can evolve

Reported history is immutable at report snapshot level:

- `reported_variants` row keeps report-time tier and key links

## How sample moves from live to done

A sample moves to done when report save updates `report_num` > 0 and pushes a report entry into `samples.reports[]`.

Until that happens, the sample remains on live list.

## Why history search results may differ from current sample view

Current sample page uses latest mutable data.

History/report pages use saved snapshot data.

So a variant can show one tier in a historical report and a newer tier in current live view.

## Why some old records behave differently

`coyote3` contains historical and newer records.

Older docs may miss newer scope fields (`assay`, `subpanel`), so compatibility rules can affect exact matching behavior.

## Practical user rule

If clinical traceability matters, always anchor decisions to saved report and report-linked history pages, not only current live sample rendering.
