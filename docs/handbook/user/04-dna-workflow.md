# DNA Workflow

This chapter documents the full DNA analyst workflow, including what happens after each user action.

## Entry point

- `/dna/sample/<sample_id>`

## What loads when the page opens

When you open a DNA sample, Coyote3:

1. Loads sample, assay config, and schema.
2. Resolves assay group and subpanel.
3. Merges sample filters with assay defaults.
4. Builds effective gene set from ASP genes + selected ISGL + ad-hoc genes.
5. Builds SNV query and loads variants.
6. Adds blacklist flags and global annotation/tier data.
7. Loads other enabled sections from assay config:
   - CNV
   - TRANSLOCATION
   - BIOMARKER
   - FUSION (if configured)

## DNA list page sections

Typical sections on `list_variants_vep.html`:

- SNV list.
- CNV list.
- Translocation list.
- Optional biomarkers/fusions sections.
- Summary/comments area.
- Coverage links and report preview action.

## Filters and sample settings behavior

On the DNA list page:

- Changing filters updates sample filter state.
- Reset returns filters to assay defaults.
- ISGL/ad-hoc settings from sample settings page immediately affect effective gene filtering.

Important behavior:

- Sample filters are mutable state on the sample.
- Later sessions see the latest saved filter values.

## Variant-level actions

Open variant detail:

- `/dna/<sample_id>/var/<var_id>`

Available actions on variant detail:

- classify tier (`/classify`)
- remove classification (`/rmclassify`)
- mark/unmark false positive (`/fp`, `/unfp`)
- mark/unmark interesting (`/interest`, `/uninterest`)
- mark/unmark irrelevant (`/irrelevant`, `/relevant`)
- add blacklist flag (`/blacklist`)
- add comments and hide/unhide comments

## Bulk actions

Route:

- `POST /dna/<sample_id>/multi_class`

Bulk actions can apply/remove:

- tiers (class docs plus text docs created in bulk path)
- false-positive flags
- irrelevant flags

## CNV actions

CNV detail route:

- `/dna/<sample_id>/cnv/<cnv_id>`

Common CNV actions:

- mark/unmark interesting
- mark/unmark false-positive
- mark/unmark noteworthy
- hide/unhide CNV comments

## Translocation actions

Translocation detail route:

- `/dna/<sample_id>/transloc/<transloc_id>`

Common translocation actions:

- mark/unmark interesting
- mark/unmark false-positive
- hide/unhide translocation comments

## Auto-tier behavior while reviewing

When variants are shown, Coyote3 checks `annotation` history and chooses latest matching classification.

Matching priority:

1. `HGVSp`
2. `HGVSc`
3. genomic identity (`CHR:POS:REF/ALT`)

Scoping:

- `solid`: assay + subpanel scoped.
- other assay groups: assay scoped.

If no direct scoped class is found, additional classification lookup may provide assay-scoped fallback.

## Report preview and save

Preview:

- `/dna/sample/<sample_id>/preview_report`

Save:

- `/dna/sample/<sample_id>/report/save`

Both use the same payload builder, so preview and saved report content are aligned.

Save path also persists:

- report file on disk
- `samples.reports[]` metadata and `report_num`
- immutable `reported_variants` snapshot rows

## Practical productive workflow

1. Start from `/samples/live`.
2. Open sample and confirm assay/subpanel context.
3. Validate effective genes before deep review.
4. Tier only after reviewing existing global annotations and assay/subpanel fit.
5. Add concise interpretation comments.
6. Preview report and verify sections.
7. Save report and verify sample appears in done/reported list.
