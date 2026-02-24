# RNA Workflow

This chapter documents the RNA fusion workflow end-to-end.

## Entry point

- `/rna/sample/<sample_id>K=`

## What loads when page opens

Coyote3:

1. Loads sample and assay context.
2. Loads RNA/fusion filter settings.
3. Builds fusion query by sample and thresholds.
4. Applies fusion effect/caller filters.
5. Loads fusions and attaches global annotations/classification.

## RNA list page actions

From list page you can:

- open fusion detail (`/rna/fusion/<fusion_id>`)
- mark fusion false-positive (`/rna/fusion/fp/<fusion_id>`)
- unmark false-positive (`/rna/fusion/unfp/<fusion_id>`)
- pick fusion call (`/rna/fusion/pickfusioncall/<fusion_id>/<callidx>/<num_calls>`)
- add sample-level comments
- hide/unhide sample comments (role restricted)
- preview report
- generate PDF report

## Fusion detail page

Route:

- `/rna/fusion/<fusion_id>`

What it shows:

- fusion metadata
- linked sample
- global annotations
- current classification

## Classification behavior

Fusion classification writes to the shared `annotation` collection with fusion-specific identity fields.

This means RNA and DNA both use the same global annotation model, but with different identity keys.

## Report actions

Preview route:

- `/rna/sample/preview_report/<sample_id>`

PDF route:

- `/rna/sample/report/pdf/<sample_id>`

Preview provides immediate render of current fusion state. PDF route generates export artifact.

## Comments flow

Sample comments are stored on sample documents and are shared context for interpretation.

Hide/unhide requires higher permissions than basic comment creation.

## Productive RNA workflow

1. Open sample from `/samples`.
2. Confirm filter thresholds and callers.
3. Review each candidate fusion and pick the correct call where needed.
4. Mark confirmed artifacts as FP.
5. Add concise comments on interpretation rationale.
6. Preview report.
7. Generate/export final report output.
