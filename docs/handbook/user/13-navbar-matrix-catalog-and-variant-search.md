# Navbar Tools: Matrix, Catalog, and Variant Search

This chapter explains the three discovery tools in the top navbar:

- `MATRIX`
- `CATALOG`
- `VARIANT SEARCH`

Use this chapter when you are not processing one sample, but instead need cross-assay discovery, panel exploration, or historical variant lookup.

Related chapters:

- [Navigation and Page Map](./03-navigation-and-pages.md)
- [Complete Click Paths](./11-complete-click-paths.md)
- [DNA Workflow](./04-dna-workflow.md)
- [RNA Workflow](./05-rna-workflow.md)

## 1. Quick decision guide (where to go)

1. Need to compare a gene across modalities/categories/lists: go to `MATRIX` (`/assay-catalog-matrix`).
2. Need to browse assay details and downloadable gene tables: go to `CATALOG` (`/assay-catalog`).
3. Need historical reported-variant and annotation search across samples: go to `VARIANT SEARCH` (`/search/tiered_variants`).

## 2. MATRIX (`/assay-catalog-matrix`)

## What it is

`MATRIX` shows a gene-by-column matrix where columns are organized as:

- modality -> category -> ISGL/list

Rows are genes; cells indicate presence/absence in each list context.

## What users can do

1. Search genes in the matrix using the search box.
2. Scan one gene horizontally to compare coverage across modalities and categories.
3. Identify whether a gene appears in one or many list contexts.
4. Use matrix as a fast triage before opening detailed catalog pages.

## How data is assembled (user-relevant behavior)

1. Matrix columns come from assay catalog modality/category/list structure.
2. For some columns, genes are sourced from ASP covered genes.
3. For others, genes are sourced from ISGL content.
4. Categories without explicit lists still render placeholder columns so service visibility is not lost.

## When to use MATRIX

- Before case setup when deciding which assay/list context includes a gene.
- During multidisciplinary review when comparing panel scope quickly.
- For high-level communication about gene coverage differences.

## 3. CATALOG (`/assay-catalog`)

## What it is

`CATALOG` is a structured browser for modalities, categories, and associated list/panel details, with live gene tables and CSV export.

## Navigation levels

1. Top level: `/assay-catalog`
2. Modality level: `/assay-catalog/<mod>`
3. Category level: `/assay-catalog/<mod>/<cat>`
4. List-focused level: `/assay-catalog/<mod>/<cat>/isgl/<isgl_key>`

## What users can do

1. Expand modality and category tree in left pane.
2. Open category/list detail in right pane.
3. Search genes, aliases, and annotations in visible gene table.
4. Export current visible gene table to CSV.
5. Open list-specific views for detailed gene context.

## CSV export behavior

CSV export path changes based on current level:

1. modality: `/assay-catalog/<mod>/genes.csv`
2. modality+category: `/assay-catalog/<mod>/<cat>/genes.csv`
3. modality+category+list: `/assay-catalog/<mod>/<cat>/isgl/<isgl_key>/genes.csv`

Use CSV export for external review, validation packs, or SOP attachments.

## When to use CATALOG

- Need structured metadata and context, not only presence/absence.
- Need downloadable gene lists from the exact current view.
- Need to inspect category-level assay descriptions and analysis information.

## 4. VARIANT SEARCH (`/search/tiered_variants`)

## What it is

`VARIANT SEARCH` is a cross-sample search for historical annotations and reported-variant context.

Access requirement:

- user must have annotation-view permissions as configured in RBAC.

## Search modes

1. `variant` (HGVSc / HGVSp / genomic identifiers)
2. `gene` (gene symbol)
3. `transcript` (transcript ID)
4. `subpanel` (sub panel name)
5. `author` (annotation author)

## Available filters

1. Search string (required for POST search).
2. Assay group multi-select filter.
3. `Include Annotation Text` checkbox.

## What happens when options are checked

1. `Include Annotation Text` checked:
- annotation text content is included in matching/evidence context where available.

2. Assay groups selected:
- search is restricted to those assay group contexts.

3. Different search mode selected:
- query interpretation changes to the corresponding field domain (variant/gene/transcript/subpanel/author).

## Results and interpretation

1. Results combine annotation hits and reported-variant sample/report links.
2. Non-variant search modes include tier statistics summary.
3. Each result can show sample context and report references.
4. From some variant pages, deep links prefill this page using URL query parameters.

## When to use VARIANT SEARCH

- Reviewing whether an event or gene has prior reporting context.
- Checking historical annotation usage across samples.
- Finding report-linked evidence before final classification/report.

## 5. End-to-end example paths

## Example A: Gene discovery to detailed panel context

1. Open `MATRIX`.
2. Search gene and identify relevant modality/category/list column.
3. Open `CATALOG`.
4. Navigate to matching modality/category/list and inspect details.
5. Export CSV if needed.

## Example B: Case review with historical evidence

1. From DNA/RNA workflow, identify gene/variant of interest.
2. Open `VARIANT SEARCH` and search by variant or gene mode.
3. Filter by assay group if needed.
4. Enable annotation text if broader context is required.
5. Review linked samples/reports and return to case workflow.

## 6. Common mistakes and fixes

1. Using CATALOG when only quick yes/no coverage is needed:
- start with MATRIX first, then drill down into CATALOG.

2. Using VARIANT SEARCH without mode alignment:
- choose mode that matches your input format (gene vs transcript vs variant).

3. Overly broad searches returning too many rows:
- add assay filter and narrow query terms.

4. Missing expected results:
- verify search mode, spelling, and assay-group filter state.

## 7. Cross-reference map

1. For sample-centric interpretation actions: [DNA Workflow](./04-dna-workflow.md), [RNA Workflow](./05-rna-workflow.md)
2. For route-level page responsibilities: [Navigation and Page Map](./03-navigation-and-pages.md)
3. For strict click-by-click operations: [Complete Click Paths](./11-complete-click-paths.md)
4. For governance/config creation actions: [Admin Creation Playbooks](./12-admin-creation-playbooks.md)
