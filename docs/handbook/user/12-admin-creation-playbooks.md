# Admin Creation Playbooks (User/Operator)

This chapter is the step-by-step operational guide for creating:

- ISGL (In Silico Gene List)
- users
- ASP (Assay Specific Panel)
- ASPC (Assay Specific Panel Config)

This document is designed so experienced operators can perform these tasks without developer assistance.

Sensitive schema/permission design internals remain in:

- `../developer/13-admin-config-permissions-and-schemas.md`

Related discovery/search guide:

- [Navbar Tools: Matrix, Catalog, and Variant Search](./13-navbar-matrix-catalog-and-variant-search.md)

## Standard terms used in this chapter

- ASP: Assay Specific Panel
- ASPC: Assay Specific Panel Config
- ISGL: In Silico Gene List

## 1. Critical prerequisites

1. You must be able to open `/admin/`.
2. Your user must have create rights for the target area.
3. At least one active schema must exist for the target entity.
4. Keep one smoke-test sample ready for immediate validation.

If no active schema exists, create pages will block with messages like:

- `No active user schemas found!`
- `No active genelist schemas found!`
- `No active panel schemas found!`
- `No active DNA schemas found!`
- `No active RNA schemas found!`

## 2. Shared form behavior (all create pages)

1. Schema selector at top-right controls which form version is used.
2. Values marked with `*` in form labels are schema-required.
3. Read-only fields are auto-filled by the system (typically audit fields).
4. On save, the system writes version metadata and audit metadata.
5. A green flash message indicates create success.

## 3. Create ISGL in detail

Entry points:

- list: `/admin/genelists`
- create: `/admin/genelists/new`

### 3.1 Required fields (active production schema `ISGL-Config` v5)

- `name`
- `displayname`
- `list_type`
- `assay_groups`
- `assays`
- `genes`

### 3.2 What each field/feature does

- `name`: internal identifier; becomes `_id`.
- `displayname`: label shown to users.
- `list_type`: controls list semantics in filtering UI. Use the expected standard value for selectable gene lists.
- `assay_groups` checkboxes:
  - checking a group shows its assay block and auto-checks its assays
  - unchecking a group hides the assay block and unchecks its assays
- `assays` checkboxes: precise assay scope inside selected groups.
- `genes` (paste or file upload):
  - if both are supplied, uploaded file is used
  - genes are deduplicated and sorted before save
- `is_active` (if present in schema): whether list is available for selection.

### 3.3 What happens on save

1. `_id` is set from `name`.
2. `genes` are parsed, cleaned, deduplicated, sorted.
3. `gene_count` is computed.
4. `schema_name` and `schema_version` are stored.
5. Version history is initialized.

### 3.4 Mandatory operator checks after create

1. Open `/admin/genelists` and verify row is present.
2. Open `/samples/<sample_id>/edit` and confirm list appears in ISGL choices.
3. Apply list and verify effective genes change.

## 4. Create User in detail

Entry points:

- list: `/admin/users`
- create: `/admin/users/new`

### 4.1 Required fields (active production schema `User-Schema` v1)

- `firstname`
- `lastname`
- `fullname`
- `username`
- `email`
- `job_title`
- `auth_type`
- `role`
- `assay_groups`
- `assays`
- `environments`
- `is_active`

Optional but available:

- `permissions`
- `deny_permissions`
- password (required operationally when `auth_type = coyote3`)

### 4.2 What each feature does

- `firstname` + `lastname`:
  - auto-populates `fullname`
  - auto-suggests lowercase `username` as `firstname.lastname`
- `username`:
  - checked live via `/admin/users/validate_username`
- `email`:
  - format validated in UI
  - checked live via `/admin/users/validate_email`
- `auth_type`:
  - `coyote3` shows password fields and enforces password strength checks in UI
  - non-`coyote3` hides password block
- password rules when visible:
  - minimum length from schema (default 10)
  - must include uppercase, lowercase, number, symbol
  - confirm must match
- `role` select:
  - auto-applies role permissions and role deny-permissions in checkbox groups
- `permissions` and `deny_permissions` checkboxes:
  - same permission cannot be checked in both lists
  - conflict blocks save button until resolved
  - at save, duplicates already included in role are removed from user-level overrides
- `assay_groups` and `assays` behavior:
  - checking a group shows assays and auto-selects all assays in that group
  - unchecking group hides and clears its assays
  - deselecting all assays in a group auto-unchecks that group
- `environments`: controls environment visibility scope.
- `is_active`: login eligibility and active account status.

### 4.3 What happens on save

1. `_id` is set to `username`.
2. `username` and `email` are lowercased.
3. Password is hashed only when `auth_type = coyote3`.
4. If not `coyote3`, password is stored as `None`.
5. `schema_name`, `schema_version`, and version-history metadata are stored.

### 4.4 Mandatory operator checks after create

1. User appears in `/admin/users`.
2. New user can log in.
3. New user can access expected pages.
4. New user cannot access restricted admin pages.
5. Worklist visibility matches assay/environment assignments.

## 5. Create ASP in detail

Entry points:

- list: `/admin/asp/manage`
- create: `/admin/asp/new`

### 5.1 Required fields (active production schema `ASP-Schema` v1)

- `assay_name`
- `display_name`
- `description`
- `asp_group`
- `asp_category`
- `asp_family`
- `type`
- `platform`
- `read_mode`
- `read_length`
- `covered_genes`
- `germline_genes`

### 5.2 What each field/feature does

- `assay_name`: internal assay key; becomes `_id`.
- `display_name`: operator-facing assay label.
- `asp_group`/`asp_category`/`asp_family`/`type`: control grouping and downstream logic selection.
- `platform`, `read_mode`, `read_length`: sequencing/runtime descriptors reused in UI/config prefill.
- `covered_genes`:
  - baseline panel gene space
  - paste or file upload supported
  - if both provided, file is used
- `germline_genes`:
  - germline gene set used in downstream filtering behavior
  - paste/file behavior matches covered genes
- `is_active` (if present): whether panel is offered for active use.

### 5.3 What happens on save

1. `_id` is set from `assay_name`.
2. `covered_genes_count` and `germline_genes_count` are computed.
3. `schema_name`, `schema_version`, `version` are stored.
4. Version history is initialized.

### 5.4 Mandatory operator checks after create

1. Panel visible in `/admin/asp/manage`.
2. Panel view page renders all metadata and gene counts.
3. Panel can be selected in ASPC create flow for matching category.

## 6. Create ASPC in detail

Entry points:

- list: `/admin/aspc`
- create DNA: `/admin/aspc/dna/new`
- create RNA: `/admin/aspc/rna/new`

### 6.1 Common create behavior

1. Select `assay_name` first.
2. UI pre-fills `display_name`, `asp_group`, `asp_category`, `platform`.
3. `environment` options are constrained to valid remaining envs for the chosen assay.
4. `_id` is generated as `<assay_name>:<environment>`.
5. Duplicate `<assay_name>:<environment>` is rejected with flash error.

### 6.2 Required fields (DNA schema `DNA-ASP-Config` v1)

- `assay_name`, `display_name`, `description`, `asp_group`, `asp_category`, `platform`, `environment`
- filters: `max_popfreq`, `max_control_freq`, `min_freq`, `min_depth`, `min_alt_reads`, `warn_cov`, `error_cov`, `min_cnv_size`, `max_cnv_size`, `cnv_gain_cutoff`, `cnv_loss_cutoff`
- selection groups: `vep_consequences`, `cnveffects`, `genelists`, `analysis_types`
- reporting: `report_header`, `report_description`, `report_method`, `report_folder`, `report_sections`, `general_report_summary`
- technical: `reference_genome`, `plots_path`, `query`, `verification_samples`, `use_diagnosis_genelist`

### 6.3 Required fields (RNA schema `RNA-ASP-Config` v1)

- `assay_name`, `display_name`, `description`, `asp_group`, `asp_category`, `platform`, `environment`
- filters: `spanning_reads`, `spanning_pairs`
- selection groups: `fusion_callers`, `fusion_effects`, `fusionlists`, `analysis_types`
- reporting: `report_header`, `report_description`, `report_method`, `report_folder`, `report_sections`, `general_report_summary`
- technical: `reference_genome`, `plots_path`, `query`, `verification_samples`, `use_diagnosis_genelist`

### 6.4 Checkbox and list behavior that affects runtime

- `use_diagnosis_genelist`:
  - when enabled, diagnosis/subpanel-specific default gene lists are automatically included in DNA sample filtering
- `vep_consequences` / `cnveffects` / `fusion_*` / `analysis_types` / `report_sections`:
  - control which filters/analysis/report sections are available and active
- `genelists` / `fusionlists`:
  - define selectable list sets connected to this assay config
- `is_active` (if present): whether config is active for runtime selection.

### 6.5 JSON fields rules

- `query` and `verification_samples` must be valid JSON objects.
- Invalid JSON can break create/update flow.
- For DNA create route, these fields are parsed explicitly from JSON before processing.

### 6.6 What happens on save

1. Config is normalized through schema-driven casting.
2. `_id` is composed as `<assay_name>:<environment>`.
3. `schema_name`, `schema_version`, `version` are stored.
4. Version history is initialized.

### 6.7 Mandatory operator checks after create

1. Config appears in `/admin/aspc`.
2. Open test sample for same assay+environment.
3. Confirm expected filters and sections in DNA/RNA pages.
4. Confirm report preview uses expected sections and header content.

## 7. Recommended rollout order

1. ASP
2. ASPC
3. ISGL
4. User assignments

This order minimizes broken references and makes validation faster.

## 8. Fast troubleshooting

1. Save button disabled on user create:
- check permission conflict (same permission in allow and deny)

2. No selectable options in create forms:
- likely no active schema or no active upstream panels

3. ASPC create blocked as duplicate:
- config for assay+environment already exists (`<assay>:<env>`)

4. ISGL/ASP gene content missing after save:
- file may have overridden pasted text
- validate uploaded file content and delimiter format
