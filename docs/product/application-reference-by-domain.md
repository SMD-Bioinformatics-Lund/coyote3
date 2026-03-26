# Application Reference By Domain

This page groups Coyote3 behavior by what users actually work with in the app:

1. Samples
2. Variants (SNV, CNV, translocation, fusion)
3. Filters (DNA + RNA)
4. Pagination

It is intended for both users and developers so everyone can map UI labels to API keys and DB fields.

## 1) Samples domain

## Why samples are the anchor

`samples` is the parent document. Most other collections point back to the same sample via `SAMPLE_ID`.

```text
assay_specific_panels (asp) ----+
                                +--> samples ----> variants
asp_configs (aspc) ------------ +              \-> cnvs
                                               \-> translocations
insilico_genelists (isgl) ----> sample.filters \-> fusions
                                               \-> panel_coverage
                                               \-> rna_expression / rna_classification / rna_qc
```

## Configuration relationship used at runtime

| Short name | Collection | Primary key | Used for |
|---|---|---|---|
| `asp` | `assay_specific_panels` | `asp_id` | Covered gene universe and assay metadata |
| `aspc` | `asp_configs` | `aspc_id` (`assay:environment`) | Environment-specific analysis/report behavior |
| `isgl` | `insilico_genelists` | `isgl_id` | Curated/adhoc selectable gene lists |

In runtime:

- `sample.assay` resolves `asp`.
- `sample.assay + sample.profile` resolves `aspc`.
- `sample.filters.genelists[]` resolves selected `isgl` documents.

## Admin ID naming and uniqueness

Admin-managed resources use business IDs (not Mongo `_id`) for create/edit/view/delete routes and lookups.

| Resource | ID key | Naming rule | Uniqueness |
|---|---|---|---|
| User | `user_id` (mirrors `username`) | lowercase login identifier | unique |
| Role | `role_id` | lowercase role slug (for example `viewer`, `admin`) | unique |
| Permission | `permission_id` | stable permission key (for example `edit_sample`) | unique |
| ASP | `asp_id` | assay identifier used by samples (`sample.assay`) | unique |
| ASPC | `aspc_id` | `<assay>:<environment>` | unique |
| ISGL | `isgl_id` | center-defined genelist identifier | unique |

Create operations validate these IDs before insert:

- If the ID already exists, API returns `409 Conflict`.
- If required IDs are missing, API returns `400`.
- UI routes always pass business IDs for `view`, `edit`, `toggle active`, and `delete`.
- Create forms perform immediate inline uniqueness checks while typing and block submit until IDs are unique.

### ASPC default list policy

For each `aspc_id` (`assay:environment`), ASPC can define default list selection policy:

- `filters.genelists` default SNV genelists
- `filters.cnv_genelists` default CNV genelists
- `filters.fusion_genelists` default fusion genelists
- `use_diagnosis_genelist` diagnosis/subpanel-driven auto-selection toggle

If those default list fields are empty, samples start with manual list selection only.

## Sample settings page: what it controls

The sample settings UI (`/edit/<sample_id>`) controls:

- Gene list selection (`genelists`)
- Adhoc genes (`adhoc_genes`)
- Effective gene scope preview
- Numeric and categorical filter values
- Comments and report history for the sample

Primary API routes behind that page:

- `GET /api/v1/samples/{sample_id}/edit-context`
- `GET /api/v1/samples/{sample_id}/genelists`
- `GET /api/v1/samples/{sample_id}/effective-genes`
- `PUT /api/v1/samples/{sample_id}/filters`
- `DELETE /api/v1/samples/{sample_id}/filters`
- `PUT /api/v1/samples/{sample_id}/genelists/selection`
- `PUT /api/v1/samples/{sample_id}/adhoc-genes`
- `DELETE /api/v1/samples/{sample_id}/adhoc-genes`

## 2) Variants domain (grouped)

## Collection and UI grouping

| UI area | Collection | Link key | Main intent |
|---|---|---|---|
| SNV/indel review | `variants` | `SAMPLE_ID` | Point variants, transcript consequences, flags |
| CNV review | `cnvs` | `SAMPLE_ID` | Copy-number segments and panel-gene impact |
| Translocation review | `translocations` | `SAMPLE_ID` | Structural DNA events |
| RNA fusion review | `fusions` | `SAMPLE_ID` | Fusion calls with caller-specific metrics |
| Clinical notes/classification | `annotations` | variant identity + nomenclature | Interpretation text and tier/class context |
| Report history snapshot | `reported_variants` | sample/report ids | Audit-safe frozen report rows |

## Tier colors and badge previews

| Tier | Badge preview | Hex |
|---|---|---|
| `Tier I` | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#d55e00;color:#fff;font-weight:600;">Tier I</span> | `#d55e00` |
| `Tier II` | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#e69f00;color:#1f2937;font-weight:600;">Tier II</span> | `#e69f00` |
| `Tier III` | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#0072b2;color:#fff;font-weight:600;">Tier III</span> | `#0072b2` |
| `Tier IV` | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#009e73;color:#fff;font-weight:600;">Tier IV</span> | `#009e73` |
| `Unclassified` | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#666666;color:#fff;font-weight:600;">Unclassified</span> | `#666666` |

## 3) Filters domain

## DNA filter keys (sample-level)

Stored under `samples.filters.*`.
SNV base behavior is configured by these filter keys. Assay-specific operator overrides are configured with:
`asp_configs.query.snv`, `asp_configs.query.cnv`, `asp_configs.query.fusion`, `asp_configs.query.transloc`.

| Key | Type | Meaning | Used by |
|---|---|---|---|
| `min_alt_reads` | int | Minimum alternate supporting reads | SNV query |
| `min_depth` | int | Minimum depth | SNV query |
| `min_freq` | float (0..1) | Minimum tumor/case AF | SNV query |
| `max_freq` | float (0..1) | Maximum tumor/case AF | SNV query |
| `max_control_freq` | float (0..1) | Maximum control AF | SNV query |
| `max_popfreq` | float (0..1) | Maximum population frequency threshold | SNV query and UI highlighting |
| `min_cnv_size` | int | Minimum CNV size | CNV query |
| `max_cnv_size` | int | Maximum CNV size | CNV query |
| `cnv_loss_cutoff` | float | Ratio threshold for loss | CNV query |
| `cnv_gain_cutoff` | float | Ratio threshold for gain | CNV query |
| `warn_cov` | int | Coverage warning threshold | DNA UI rendering |
| `error_cov` | int | Coverage error threshold | DNA UI rendering |
| `vep_consequences` | list[str] | Consequence groups expanded to SO terms | SNV query |
| `cnveffects` | list[str] | CNV effect groups (`loss`, `gain`) | CNV post-filtering |
| `genelists` | list[str] | Selected ISGL ids | Effective gene scope + query filtering |
| `cnv_genelists` | list[str] | Selected CNV ISGL ids | CNV gene-scope filtering |

## RNA filter keys (sample-level)

| Key | Type | Meaning | Used by |
|---|---|---|---|
| `min_spanning_reads` | int | Minimum supporting split/span reads | Fusion query |
| `min_spanning_pairs` | int | Minimum supporting pairs | Fusion query |
| `fusion_callers` | list[str] | Selected callers (canonicalized) | Fusion query |
| `fusion_effects` | list[str] | Selected effects (`in-frame`, `out-of-frame`) | Fusion query |
| `fusionlists` | list[str] | Selected fusion list ids | Fusion context and gene filtering |

## Prefix normalization (form key to canonical key)

| Prefix in form payload | Canonical key in `samples.filters` |
|---|---|
| `vep_*` | `vep_consequences` |
| `genelist_*` | `genelists` |
| `cnveffect_*` | `cnveffects` |
| `fusioncaller_*` | `fusion_callers` |
| `fusioneffect_*` | `fusion_effects` |
| `fusionlist_*` | `fusionlists` |

## Query operators used in backend filters

Mongo operators used by DNA/RNA query logic include:

- `$gte`, `$lte` for threshold bounds
- `$in` for selected lists (genes, consequence terms, callers/effects)
- `$elemMatch` for nested arrays (`GT`, `INFO.CSQ`, `calls`)
- `$or`, `$and` for combined criteria
- `$exists`, `$type`, `$not` for missing/typed value handling
- `$regex` (RNA fusion list descriptors such as known/mitelman)

ASPC query overrides under `asp_configs.query.<domain>` accept Mongo operator objects directly
(for example `$or`, `$and`, `$nor`, `$expr`, field predicates), where `<domain>` is
`snv`, `cnv`, `fusion`, or `transloc`.

## 4) Pagination domain

## Samples list pagination (server-side)

Samples home uses server-side pagination for two independent tables:

- Live table
- Done/Reported table

API request keys:

- `live_page`, `live_per_page`
- `done_page`, `done_per_page`
- `page`, `per_page`

API response includes:

- `has_next_live`
- `has_next_done`

UI query params:

- `lp`
- `dp`
- `lpp`
- `dpp`

## In-page table pagination (client-side)

Some pages also use client-side pagination via `coyote/static/js/pagination.js`.

This mode paginates rows already loaded in the browser using:

- `.pagination` container
- `data-rows-per-page`
- previous/next controls

Use server-side pagination for large datasets and client-side pagination for already small, locally rendered tables.

## Practical consequences for users

1. Filters are persisted at sample level, so reopening the sample preserves review context.
2. Selected ISGL and adhoc genes directly change the effective analysis scope.
3. Tier badges and filter badges are visual shortcuts backed by stable DB/API fields.
4. Live and reported samples paginate independently, so moving in one list does not reset the other.

## Time handling

- API and database timestamps are stored in UTC (ISO-8601).
- UI renders timestamps in the viewer's local timezone.
