# Sample landing page & gene list workflow

## What this page is for

A fast, clean overview of a sample with clear meta, file/QC status, and a *clinically useful* gene filtering workflow:

* highlight key meta (DNA, Illumina, Panel, GRCh38, assay, pipeline, profile)
* view file presence/counts
* select assay-specific gene lists and/or add *ad-hoc* (case-specific) genes
* see the **Effective Genes** used for analysis and reports
* read all analyst comments with markdown rendering

---

## Key concepts

* **ISGLs**: curated in-silico gene lists bound to one or more assays. Stored globally; referenced on a sample via `filters.genelists` (by id/name per your handler).
* **Ad-hoc genes**: per-sample, analysis-specific lists, saved at `filters.ad_hoc_genes`.
* **Effective genes**: the set actually used for variant display/filtering:

  * If any ISGL or ad-hoc genes exist → `unique(ISGL ∪ ad_hoc)`
  * Else → full assay gene list

---

## Page layout

1. **Overview** (left)
   Case & Control blocks with run/pool/reads; paired/unpaired badge.

2. **Key Meta** (right, top)
   Bold chips for **DNA**, **Illumina**, **Panel**, **GRCh38**, **Assay**, **Pipeline vX**, **Profile**, **Case**, **Added**.

3. **Files & QC** (right, below)
   Reusable rows (VCF, CNV JSON, Coverage JSON, CNV Profile) with Present/Missing and optional counts (SNVs/CNVs). Copy-path button optional.

4. **Gene list actions**

   * **Choose Gene Lists**: opens a modal listing available temporary ISGLs for the assay; select one or many and **Apply selected**.
   * **Paste Ad-hoc Genes**: label + genes (comma/space/newline separated). Saves to the sample.

5. **Effective Genes**

   * Summary: “*X selected from Y*” (or “Using assay default (Y)”)
   * Preview list (≤ 40). **View all** opens full modal.

6. **Comments**

   * “View all comments (N)” opens a modal, newest first, markdown rendered (headings, lists, tables).

---

## How to use (analyst workflow)

1. Open a sample. Confirm **Key Meta** looks right.
2. Check **Files & QC** — all Present? If missing, fix upstream.
3. Click **Choose Gene Lists** to select one or more temporary ISGLs relevant for this analysis. Click **Apply selected**.
4. If needed, click **Paste Ad-hoc Genes** to add case-specific targets (e.g., transplant focus). Save.
5. Check **Effective Genes** — confirms how many are active; skim preview; click **View all** if needed.
6. Proceed to variant review. The same effective set is used by your filters/report generation (as designed).
7. Add notes in **Comments**; use markdown for structure (`##`, lists, tables).

---

## Backend endpoints

* **List available temp ISGLs**

  * `GET /samples/<sample_id>/temp-isgls`
  * Response: `{ ok: true, items: [{_id,name,version,gene_count}, ...] }`

* **Apply selected ISGLs to sample (bulk)**

  * `POST /samples/<sample_id>/temp-genes/apply-isgl`
  * Body: `{ "isgl_ids": ["...","..."] }`
  * Effect: merges genes from those ISGLs into `filters.ad_hoc_genes` **or** stores provenance + effective set (depending on your chosen design). We currently merge into the sample’s ad-hoc effective set.

* **Paste ad-hoc genes**

  * `POST /samples/<sample_id>/temp-genes`
  * Body: `{ "label": "Transplant focus", "genes": "DNMT3A TET2 ASXL1 ..." }`
  * Normalizes to uppercase unique list, stored at `filters.ad_hoc_genes`.

* **Clear ad-hoc**

  * `POST /samples/<sample_id>/temp-genes/clear`

* **Effective genes (preview / full)**

  * `GET /samples/<sample_id>/effective-genes?limit=40` → preview counts/chips
  * `GET /samples/<sample_id>/effective-genes/all` → `{ items: [ ... ] }` full flat list

> Access control: `@require_sample_access` on all; add your `@require(...)` roles to the POSTs.

---

## Data model (relevant fields)

```json
sample.filters = {
  "genelists": ["ISGL_ID_OR_NAME", ...],        // selected curated ISGLs
  "ad_hoc_genes": {
    "label":  "LABEL", 
    "genes": ["DNMT3A","TET2","ASXL1"]
    }    // per-sample added genes
}
```

---

## UI details

### Files & QC macro

* Macro: `file_row(label, path, present, icon=None, extra_badge=None, missing_msg="…")`
* Present/Missing badge; optional count badge (e.g., `23 SNVs`).
* Path is truncated; optional copy button.

### Effective Genes

* Frontend calls backend; renders summary + up to 40 chips.
* If more, “View all” opens modal with full list.

### Comments modal

* Sorted newest → oldest.
* Uses `render_markdown` filter.
* Styled with Tailwind `prose` (or minimal CSS).

### Markdown rendering

* Filter name: `render_markdown`; alias to `markdown` if you want.
* Wrap output in `<div class="prose prose-sm max-w-none">...</div>` so headings show.

---

## Troubleshooting

* **Markdown not styled**: the HTML is there, but CSS reset flattens it. Wrap in `prose` or add heading styles.
* **Modal doesn’t open**: check that the button and modal IDs match; scripts run after DOM (`defer` or `DOMContentLoaded`); ensure open/close toggles `hidden`/`flex`.
* **Jinja errors (‘globals’ undefined)**: use `environment.filters` to check for filters; don’t call Python built-ins (e.g., `bool()`) in templates.
* **Apply selected does nothing**: confirm `POST /temp-genes/apply-isgl` exists, returns `{ok:true}`, and your JS posts `{ isgl_ids:[...] }`.

---
