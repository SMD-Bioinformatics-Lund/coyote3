# End-to-End Process Flows

This chapter maps complete request-to-persistence flows for major Coyote3 workflows.

## 1. Login and route guard flow

1. User authenticates through login routes.
2. Request lifecycle loads user context.
3. Route decorators validate permission and sample scope.
4. Unauthorized requests terminate before business logic.

## 2. Samples worklist flow (`/samples`)

Handler: `home_bp.samples_home`

1. Parse search and status state.
2. Resolve user assay/environment scope.
3. Optionally narrow assays by path parameters.
4. Query done and/or live samples through `SampleHandler.get_samples`.
5. Apply recent-window constraint for done list when no active search.
6. Render worklist template.

## 3. Sample settings flow (`/samples/<sample_id>/edit`)

1. Load sample and assay configuration.
2. Initialize missing sample filters from assay defaults.
3. Compute effective gene set from ASP + ISGL + ad-hoc genes.
4. Compute raw and filtered variant statistics.
5. Render settings page.

Supporting sample-settings routes modify `sample.filters` directly.

## 4. DNA list flow (`/dna/sample/<sample_id>`)

1. Load sample/config/schema.
2. Resolve assay group and subpanel.
3. Merge sample filter state with assay defaults.
4. Compute effective gene filter set.
5. Build and execute variant query.
6. Add blacklist metadata.
7. Add global annotation and classification context.
8. Build section-specific display data (SNV/CNV/translocation/biomarker).
9. Render DNA list template.

## 5. Auto-tier resolution flow

Handler: `AnnotationsHandler.get_global_annotations`

1. Build variant identity set in priority order (`p`, `c`, `g`).
2. Query annotation records by gene + identity.
3. Resolve latest scoped class for current assay context.
4. For `solid`, include subpanel matching.
5. Fallback to class `999` when scoped classification is absent.
6. Optionally attach transcript-aware alternative class.

## 6. Manual classification flow

Routes:

- `/dna/<sample_id>/var/<var_id>/classify`
- `/dna/<sample_id>/multi_class`
- `/dna/<sample_id>/var/<var_id>/rmclassify`

Behavior:

- create class records in `annotation`
- create text records in bulk classification path
- remove scoped class records through unclassify action

## 7. Flag and comment mutation flow

Mutations include:

- false-positive flags
- interesting/irrelevant/noteworthy flags
- comment hide/unhide operations

These actions update event or sample comment state, then redirect back to case workspace.

## 8. DNA report preview flow

Route:

- `/dna/sample/<sample_id>/preview_report`

Behavior:

- builds report payload using shared report builder
- renders HTML preview
- performs no file or database writes

## 9. DNA report save flow

Route:

- `/dna/sample/<sample_id>/report/save`

Persistence sequence:

1. Generate report identifier and output path.
2. Build report payload with snapshot rows.
3. Write report HTML artifact.
4. Append report metadata and increment `report_num` in sample.
5. Upsert immutable snapshot rows in `reported_variants`.
6. Redirect to worklist with reload.

## 10. Historical interpretation flow

Routes:

- `/reported_variants/variant/<variant_id>/<tier>`
- `/search/tiered_variants`

Behavior:

- resolve current annotation and historical report linkage
- enrich results with sample/report references
- provide report-time interpretation traceability

## 11. RNA workflow summary

Route:

- `/rna/sample/<id>K=`

Flow:

1. Load sample and fusion filter state.
2. Build fusion query by thresholds/effects/callers.
3. Load fusion rows.
4. Attach global annotation/classification context.
5. Render list and detail pages.
6. Render preview/PDF report outputs.

## 12. Admin versioned-configuration flow

For users/roles/permissions/ASP/ASPC/ISGL:

1. Parse and validate form payload.
2. Increment version metadata.
3. Store version-history hash/delta.
4. Persist updated document.
5. Support rewind through delta application when requested.
