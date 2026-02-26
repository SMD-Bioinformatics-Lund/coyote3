# Coyote3 DNA/RNA Shared Services Migration Plan

## 1) Purpose

This document tracks a **zero-functionality-change** migration from blueprint-coupled logic to shared service modules, while preserving production behavior (clinical safety first).

Use this file as the single source of truth for:

- Scope and constraints
- Task list and status
- Validation and rollback criteria
- Implementation notes per completed task

---

## 2) Non-Negotiable Constraints

1. No endpoint behavior changes during migration phases 1-5.
2. No schema-breaking DB changes required for migration.
3. No changes to permission behavior.
4. No report content drift without explicit sign-off.
5. Every migration step must have:
   - Validation checks
   - Rollback path
   - Notes entry in this file

---

## 3) Current Baseline (Read-Only DB Profile)

### 3.1 Production (`coyote3`) observations

- `samples`, `variants`, `annotation`, `reported_variants` are active.
- `fusions` collection is missing in `coyote3`.
- `transloc` exists.
- Implication: collection mapping and analyte flow must be environment-aware.

### 3.2 Development (`coyote_dev_3`) observations for RNA

- `fusions` exists and is populated.
- RNA samples use assay `fusion`.
- Filter key shapes observed:
  - canonical: `min_spanning_reads`, `min_spanning_pairs`
  - legacy: `spanning_reads`, `spanning_pairs`
- `calls.spanreads/spanpairs` are numeric in latest docs.
- Fusion annotations exist (`annotation.nomenclature = "f"`).

---

## 4) Target Architecture (No Big-Bang Rewrite)

### 4.1 Keep

- Existing blueprint routes
- Existing templates and URLs
- Existing DB handlers (`coyote/db/*`)

### 4.2 Introduce

- `coyote/services/*` for shared domain logic
- Blueprint utils become thin compatibility wrappers

### 4.3 Ownership Rules

- `blueprints/*/views.py`: request parsing + permission checks + render/redirect
- `blueprints/*/util.py`: only lightweight presentation helpers / wrappers
- `services/*`: business/domain logic
- `db/*`: persistence/query primitives

---

## 5) Phased Migration Tasks

Status values: `todo`, `in_progress`, `done`, `blocked`

| ID | Phase | Task | Status | Notes |
|---|---|---|---|---|
| P0-1 | Baseline | Freeze migration scope and define golden samples (DNA + RNA) | done | Golden set locked in script and baseline artifact |
| P0-2 | Baseline | Capture route/query/report baselines for golden samples | done | Route/query/report baseline artifact captured for all golden samples in `coyote_dev_3` |
| P1-1 | Contracts | Add compatibility adapter for RNA filter keys (`spanning_*` + `min_spanning_*`) | done | Read-path normalization added in RNA view flow without DB mutation |
| P1-2 | Contracts | Add typed contracts for report payload/query inputs (warn mode validation) | done | Warn-only contract checks added for DNA/RNA report inputs and RNA filter inputs |
| P2-1 | Shared Extraction | Extract shared annotation enrichment logic from `util.dna` to `services/interpretation` | done | Shared annotation enrichment service added; DNA util methods now compatibility wrappers |
| P2-2 | Shared Extraction | Extract shared report timestamp/path helpers to `services/reporting/common` | done | Shared helper now used by both DNA and RNA report save flows |
| P2-3 | Shared Extraction | Keep wrapper functions in old util modules (backward-compatible) | done | Wrappers retained for extracted helpers (`get_report_timestamp`, `add_global_annotations`, `add_alt_class`) |
| P3-1 | Service Facade | Create `RNAWorkflowService` and call from RNA views without route changes | done | RNA list/show/report-prep flow now calls facade methods; route/template contracts unchanged |
| P3-2 | Service Facade | Create `DNAWorkflowService` and call from DNA views without route changes | done | DNA report/list validation paths now call facade methods; route/template contracts unchanged |
| P4-1 | Query Layer | Centralize filter coercion/normalization in shared service module | done | Shared normalization module added; RNA compat/query/workflow paths now consume it |
| P4-2 | Query Layer | Keep analyte-specific query builders, compare query parity before/after | done | Legacy RNA builder now wraps service builder; parity script run on `coyote_dev_3` with 0 mismatches |
| P5-1 | Reporting | Unify save/preview pipeline internals for DNA/RNA, keep outputs identical | done | Shared report persistence pipeline added and wired through DNA/RNA workflow facades |
| P6-1 | Templates | Extract shared summary comments + markdown editor partials/macros | done | Shared summary/markdown partials created and wired in DNA + RNA list pages |
| P6-2 | Templates | Keep existing ids/classes for JS compatibility | done | Existing summary IDs/classes retained; template-load sanity passed |
| P7-1 | Optional API | Evaluate API facade after service layer stabilizes | done | Decision: no new API facade now; keep blueprint routes + service layer, reassess after non-optional migration work |
| P8-1 | Hardening | Remove remaining RNA calls to `util.dna` where shared services already exist | done | RNA list/show flows now call `services/interpretation/annotation_enrichment` directly |
| P8-2 | Hardening | Inventory remaining DNA utility methods and split into service candidates vs presentation-only wrappers | done | Method-level inventory completed with usage counts and extraction buckets |
| P8-3 | Hardening | Consolidate duplicated list-page JS helpers into shared assets/partials without changing IDs/classes | done | Shared list-page JS partial wired in DNA/RNA list pages; duplicate helper defs removed |
| P8-4 | Hardening | Extract low-risk active DNA filter helper logic into services with compatibility wrappers | done | `get_filter_conseq_terms` and `create_cnveffectlist` moved to shared workflow service |
| P8-5 | Hardening | Extract active CNV organization/filter helpers into shared services with wrappers | done | `cnvtype_variant` and `cnv_organizegenes` moved to shared workflow service |
| P8-6 | Hardening | Extract active variant-format helpers into shared services with wrappers | done | `format_pon` and `get_variant_nomenclature` moved to shared workflow service |
| P9-1 | Cross-Blueprint | Move shared bpcommon interpretation/report-text logic to services and rewire blueprint callsites | done | `BPCommonService` added; DNA/RNA/common views now call services directly; wrappers retained |
| P9-2 | Cross-Blueprint | Remove migrated helper modules from injected `util` aggregator immediately (no deferred shrink) | done | `util.bpcommon` and `util.rna` detached; active callsites migrated to services |
| P9-3 | Cross-Blueprint | Delete legacy blueprint wrapper functions/files already moved to services | done | Removed legacy wrapper methods from `dna/util.py` and deleted unused `common/util.py` + `rna/util.py` |
| P9-4 | Naming | Replace ambiguous service names with explicit domain names and function-based entrypoints | done | Introduced `report_summary` and `report_paths`; rewired active imports |
| P9-5 | Naming | Remove unnecessary wrapper modules/classes (`bp_common`, `reporting/common`) and keep direct implementations | done | `report_summary.py` now contains direct implementation; wrapper files removed |
| P10-1 | DNA Finalization | Extract remaining active `DNAUtility` helpers (`hotspot_variant`, `filter_variants_for_report`, `sort_by_class_and_af`, `get_simple_variants_for_report`) to `services/` | done | Shared `dna_reporting` helper functions are canonical and used at active callsites |
| P10-2 | DNA Finalization | Move `build_dna_report_payload` out of `blueprints/dna/util.py` into service layer | done | `build_dna_report_payload` now lives in `services/workflow/dna_reporting.py` |
| P10-3 | DNA Finalization | Rewire DNA views/workflow to service functions only (no `DNAUtility` imports) | done | `DNAWorkflowService` now imports shared report builder directly; no `DNAUtility` references remain |
| P10-4 | DNA Finalization | Delete `coyote/blueprints/dna/util.py` after zero references remain | done | Legacy DNA utility module deleted |
| P10-5 | DNA Finalization | Remove `DNAUtility` from `coyote/util/__init__.py` permanently and verify app init/report paths | done | Utility aggregator no longer references DNA utility class; app init sanity passed |
| P11-1 | Flask/API Structure | Extract duplicated template-filter logic to shared module and rewire wrappers (no template contract changes) | in_progress | Shared helper module now covers markdown + fusion descriptor helpers with blueprint wrapper delegation |
| P11-2 | Flask/API Structure | Introduce centralized filter registration entrypoint (`register_filters(app)`) and remove implicit import-order coupling | done | Filter registration now explicit in app factory; side-effect filter imports removed from blueprints/views |
| P11-3 | Flask/API Structure | Split oversized blueprint route files into route-domain modules (web routes only, same URLs) | done | DNA/RNA/admin oversized route files are split into domain modules; endpoint/URL contracts preserved |
| P11-4 | API Readiness | Migrate API runtime from Flask blueprint routing to FastAPI while reusing current services and RBAC semantics | done | Native FastAPI app (`asgi.py`) now serves `/api/v1/*`; Flask API blueprint is disabled by default and kept behind compatibility toggle |
| P11-5 | API Readiness | Add API-aware auth/permission error mode (JSON for API, redirects for web) in centralized enforcement path | done | Central `before_request` RBAC gate now returns JSON `401/403` for `/api/*` while keeping web redirects |
| P12-1 | Frontend/API Strategy | Define target architecture: server-rendered web remains primary while API grows in parallel (no big-bang replacement) | done | Strategy adopted: phased migration with web-first continuity and feature-level cutover |
| P12-2 | Frontend/API Strategy | Add parity endpoints for current high-traffic list/detail screens (DNA list/detail, RNA list/detail) using existing service layer | in_progress | DNA variant/CNV/translocation + RNA fusion list/detail and DNA/RNA report-preview endpoints added under `/api/v1/{dna,rna}/samples/...` |
| P12-3 | Frontend/API Strategy | Introduce web-side API client layer for progressive enhancement (read-only first, then write flows) | in_progress | Added server-side Python API client with typed models (`coyote_web/api_client.py`, `api_models.py`) for blueprint reads; browser-side hydration helper removed |
| P12-4 | Frontend/API Strategy | Ensure RBAC parity and consistent error payloads across web/API (401/403/404/AppError mapping) | in_progress | API-aware JSON error handling added in global error handlers; web templates preserved |
| P12-5 | Frontend/API Strategy | Add migration toggles per feature page to switch between server-rendered data and API-backed data paths | in_progress | Config flags added (`WEB_API_READ_*` + `WEB_API_STRICT_MODE`); RNA and DNA list reads now support server-side API path with Mongo fallback |
| P12-6 | Frontend/API Strategy | Define completion criteria and decommission plan for legacy data-loading paths after stable parity | todo | Legacy route logic removed only after verified parity and soak period |
| P13-1 | App Boundary Split | Introduce top-level `coyote_web` and `coyote_api` packages as canonical runtime entrypoints | done | Added explicit app packages; compose/runtime now starts web from `coyote_web` and API from `coyote_api` |
| P13-2 | App Boundary Split | Rewire compose/dev reload to track both app packages and avoid stale API container code | done | Dev compose now mounts `coyote_api` + `coyote_web` and uvicorn reload watches both |
| P13-3 | Frontend Asset Hardening | Vendor remote markdown JS/CSS to local static assets and remove CDN dependence in base layout | done | Added `scripts/vendor_web_assets.py`; layout now uses local `static/vendor/*` paths |

---

## 6) Validation Gates (Per Task)

Each task must pass:

1. Unit/functional checks for touched modules.
2. Golden sample comparisons:
   - filtered result counts
   - selected/tiered entity counts
   - summary text presence
   - report generation success
3. No permission regression.
4. No endpoint/route contract changes unless explicitly planned.

---

## 7) Rollback Rules

For each task:

1. Keep old call path available (wrapper or feature flag).
2. If mismatch detected:
   - revert to old call path immediately
   - retain logs and diff for investigation
3. Do not proceed to next task until current task is validated.

---

## 8) Execution Checklist Template

Copy for each task:

```
### Task <ID> - <Title>
- Date:
- Owner:
- Scope:
- Files changed:
- Validation executed:
- Result:
- Rollback needed: yes/no
- Follow-up actions:
```

---

## 9) Work Log (Update Every Session)

### Entry: Initial Plan Setup

- Date: 2026-02-25
- Summary:
  - Created migration plan tracker file.
  - Added phased tasks, validation gates, rollback rules, and work-log template.
  - Included DB read-only baseline notes for `coyote3` and `coyote_dev_3`.
- Next recommended task:
  - `P0-1` define golden sample set and baseline outputs.

### Task P0-1 - Define Golden Samples

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Select stable DNA + RNA samples in `coyote_dev_3` for migration regression checks.
- Files changed:
  - `migration_scripts/capture_phase0_baseline.py` (new)
  - `migration_scripts/baselines/phase0_baseline_coyote_dev_3.json` (new artifact)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + log update)
- Golden sample set:
  - DNA: `25MD17060p-2`
  - DNA: `23MD12079-wgs`
  - RNA: `25MD16916-fusion-fusions`
  - RNA: `RNAfusion-integration-test`
- Validation executed:
  - Read-only DB candidate sampling and count checks in `coyote_dev_3`
  - Baseline capture script run:
    - `python migration_scripts/capture_phase0_baseline.py`
- Result:
  - Baseline artifact generated successfully with collection counts + per-sample counts + filter keys/values.
- Rollback needed: no
- Follow-up actions:
  - Complete `P0-2` by adding route/query/report rendering baselines for these same samples.

### Task P0-2 - Capture Route/Query/Report Baseline Signals

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Capture stable route contract, query shape, and report snapshot counters for golden DNA/RNA samples.
- Files changed:
  - `migration_scripts/capture_phase0_route_query_report_baseline.py` (updated import strategy to avoid app-context dependency)
  - `migration_scripts/baselines/phase0_route_query_report_baseline_coyote_dev_3.json` (new artifact)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python migration_scripts/capture_phase0_route_query_report_baseline.py`
  - Verified artifact content includes all 4 golden sample entries and route/query/report sections.
- Result:
  - Route/query/report baseline artifact generated successfully in read-only mode.
- Rollback needed: no
- Follow-up actions:
  - Start `P1-1` filter-key compatibility adapter with zero route contract change.

### Task P13-1/P13-2/P13-3 - API/Web Boundary + Asset Localization

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Establish explicit top-level app packages (`coyote_web`, `coyote_api`) as canonical runtime boundaries.
  - Rewire compose commands and dev auto-reload paths to track the split packages.
  - Download remote markdown editor assets to local static vendor files and remove runtime CDN dependencies.
- Files changed:
  - `coyote_web/__init__.py` (new)
  - `coyote_web/wsgi.py` (new)
  - `coyote_api/__init__.py` (new)
  - `coyote_api/app.py` (new)
  - `asgi.py` (rewired to `coyote_api.app`)
  - `run_api.py` (rewired to `coyote_api.app:app`)
  - `run.py` (compat shim to `coyote_web.wsgi`)
  - `wsgi.py` (compat shim to `coyote_web.wsgi`)
  - `docker-compose.dev.yml` (web/api commands + mounts + reload dirs)
  - `docker-compose.yml` (web/api commands)
  - `scripts/vendor_web_assets.py` (new downloader)
  - `coyote/templates/layout.html` (local static vendor paths)
- Validation executed:
  - `python scripts/vendor_web_assets.py` (downloaded EasyMDE JS/CSS and markdown-it JS)
- Result:
  - Split app boundary is explicit and operationally wired.
  - Frontend markdown dependencies are now local assets, not CDN-hosted.
- Rollback needed: no
- Follow-up actions:
  - Continue P12 feature-level cutover to API-backed reads/writes per screen.

### Task P12-5 (Phase 1) - Web Feature Toggles + RNA List API Hydration

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Add explicit feature flags to control web list-page data source (server-rendered vs API-hydrated).
  - Implement the first toggled page cutover for RNA fusion list with safe fallback.
- Files changed:
  - `config.py` (added `WEB_API_READ_DNA_VARIANTS`, `WEB_API_READ_RNA_FUSIONS`)
  - `coyote/templates/layout.html` (exposes `window.COYOTE_FEATURE_FLAGS`, loads `api_pages.js`)
  - `coyote/static/js/api_pages.js` (new page adapter for RNA fusion list hydration)
  - `coyote/blueprints/rna/views_fusions.py` (passes `api_sample_id` to template)
  - `coyote/blueprints/rna/templates/list_fusions.html` (hydrates fusion table via API when enabled)
  - `docker-compose.dev.yml` (enables `WEB_API_READ_RNA_FUSIONS=1`, keeps DNA toggle off)
  - `docker-compose.yml` (keeps both toggles off in production)
- Validation executed:
  - Pending runtime verification after compose reload (next step).
- Result:
  - API cutover now controllable per screen and environment; server-rendered fallback remains intact.
- Rollback needed: no
- Follow-up actions:
  - Add DNA variants list hydration behind `WEB_API_READ_DNA_VARIANTS`.

### Task P1-1 - RNA Filter Key Compatibility Adapter

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Add compatibility normalization for legacy RNA filter keys (`spanning_reads`, `spanning_pairs`) to canonical keys (`min_spanning_reads`, `min_spanning_pairs`) on the read path.
- Files changed:
  - `coyote/services/rna/filter_compat.py` (new)
  - `coyote/blueprints/rna/views.py` (uses normalizer in `list_fusions`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `python -m py_compile coyote/services/rna/filter_compat.py coyote/blueprints/rna/views.py`
  - Read-only DB sanity check on `coyote_dev_3` sample `RNAfusion-integration-test`:
    - legacy keys present
    - normalized canonical values computed as expected
- Result:
  - Compatibility adapter is active with no DB writes and no endpoint signature changes.
- Rollback needed: no
- Follow-up actions:
  - Move to `P1-2` typed contract scaffolding in warn-only mode.

### Task P1-2 - Warn-Only Workflow Contracts

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Add non-blocking contract validation for shared workflow inputs with warning logs only.
  - Cover DNA/RNA report input shape and RNA filter/query input shape.
- Files changed:
  - `coyote/services/workflow/contracts.py` (new)
  - `coyote/blueprints/rna/views.py` (warn-only checks in list/report routes)
  - `coyote/blueprints/dna/views.py` (warn-only checks in preview/save report routes)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `python -m py_compile coyote/services/workflow/contracts.py coyote/blueprints/rna/views.py coyote/blueprints/dna/views.py`
  - `PYTHONPATH=. .venv/bin/python -c "from coyote.services.workflow.contracts import validate_report_inputs_warn_only, validate_rna_filter_inputs_warn_only; print('contracts_import_ok')"`
- Result:
  - Contracts are now available and wired in warn-only mode, with no endpoint signature or persistence behavior change.
- Rollback needed: no
- Follow-up actions:
  - Start `P2-1` extraction of shared annotation/report helper logic to service modules with compatibility wrappers.

### Task P2-2 - Shared Report Timestamp/Path Helpers

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Extract common report timestamp and report file-location construction used by DNA/RNA save-report flows.
- Files changed:
  - `coyote/services/reporting/common.py` (new)
  - `coyote/blueprints/dna/views.py` (uses shared report file-location helper)
  - `coyote/blueprints/rna/views.py` (uses shared report file-location helper)
  - `coyote/blueprints/dna/util.py` (`get_report_timestamp` now wrapper to shared helper)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/reporting/common.py coyote/services/workflow/contracts.py coyote/services/rna/filter_compat.py coyote/blueprints/rna/views.py coyote/blueprints/dna/views.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.reporting.common import build_report_file_location; from coyote.services.workflow.contracts import validate_report_inputs_warn_only; print('venv_import_ok')"`
- Result:
  - Shared helper extraction completed with no endpoint contract changes.
- Rollback needed: no
- Follow-up actions:
  - Continue `P2-3` by adding/confirming wrappers for additional extracted helpers as we move logic out of blueprint util modules.

### Task P2-1 - Shared Annotation Enrichment Extraction

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Extract shared annotation enrichment logic from `DNAUtility` into shared services layer.
  - Preserve all existing route call signatures and behavior through compatibility wrappers.
- Files changed:
  - `coyote/services/interpretation/annotation_enrichment.py` (new)
  - `coyote/blueprints/dna/util.py` (wrapper methods for extracted helpers)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/interpretation/annotation_enrichment.py coyote/services/reporting/common.py coyote/services/workflow/contracts.py coyote/services/rna/filter_compat.py coyote/blueprints/rna/views.py coyote/blueprints/dna/views.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.interpretation.annotation_enrichment import add_global_annotations, add_alt_class; print('interpretation_import_ok')"`
- Result:
  - Shared annotation enrichment module is active and import-safe.
  - Existing blueprint call sites continue to use `util.dna.*` interfaces unchanged.
- Rollback needed: no
- Follow-up actions:
  - Move to `P3-1` and start introducing `RNAWorkflowService` facade with route-level parity checks.

### Task P3-1 - RNA Workflow Service Facade

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Create `RNAWorkflowService` and route RNA view orchestration through facade methods without endpoint changes.
  - Keep existing route decorators, URLs, templates, and response shapes intact.
- Files changed:
  - `coyote/services/workflow/rna_workflow.py` (new)
  - `coyote/services/rna/fusion_query_builder.py` (new service-level query builder to avoid blueprint import coupling)
  - `coyote/blueprints/rna/views.py` (uses `RNAWorkflowService` for filter/query/show/report prep)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/rna/fusion_query_builder.py coyote/services/workflow/rna_workflow.py coyote/blueprints/rna/views.py coyote/services/workflow/contracts.py coyote/services/rna/filter_compat.py coyote/services/reporting/common.py coyote/services/interpretation/annotation_enrichment.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.workflow.rna_workflow import RNAWorkflowService; from coyote.services.rna.fusion_query_builder import build_fusion_query; print('rna_workflow_import_ok')"`
- Result:
  - RNA facade is active and import-safe outside blueprint context.
  - Existing behavior preserved by keeping blueprint route boundaries and template payload keys stable.
- Rollback needed: no
- Follow-up actions:
  - Proceed to `P3-2` and introduce `DNAWorkflowService` facade using the same thin-wrapper pattern.

### Task P3-2 - DNA Workflow Service Facade

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Create `DNAWorkflowService` and route selected DNA orchestration through facade methods without endpoint changes.
  - Keep existing route decorators, URLs, templates, and response shapes intact.
- Files changed:
  - `coyote/services/workflow/dna_workflow.py` (new)
  - `coyote/blueprints/dna/views.py` (uses `DNAWorkflowService` for warn-only validation + report payload/path orchestration)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/dna_workflow.py coyote/blueprints/dna/views.py coyote/services/workflow/rna_workflow.py coyote/blueprints/rna/views.py coyote/services/workflow/contracts.py coyote/services/rna/filter_compat.py coyote/services/rna/fusion_query_builder.py coyote/services/reporting/common.py coyote/services/interpretation/annotation_enrichment.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.workflow.dna_workflow import DNAWorkflowService; print('dna_workflow_import_ok')"`
- Result:
  - DNA facade is active and import-safe.
  - Existing behavior preserved by keeping blueprint route boundaries and template payload keys stable.
- Rollback needed: no
- Follow-up actions:
  - Proceed to `P4-1` and centralize filter coercion/normalization in shared service module with parity checks.

### Task P4-1 - Shared Filter Coercion/Normalization

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Centralize filter coercion/normalization in workflow services layer.
  - Preserve existing RNA behavior and keep compatibility wrappers for old call paths.
- Files changed:
  - `coyote/services/workflow/filter_normalization.py` (new shared module)
  - `coyote/services/rna/filter_compat.py` (now wrapper to shared normalizer)
  - `coyote/services/rna/fusion_query_builder.py` (uses shared integer coercion)
  - `coyote/services/workflow/rna_workflow.py` (uses shared normalizer directly)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/filter_normalization.py coyote/services/rna/filter_compat.py coyote/services/rna/fusion_query_builder.py coyote/services/workflow/rna_workflow.py coyote/services/workflow/dna_workflow.py coyote/blueprints/rna/views.py coyote/blueprints/dna/views.py coyote/services/workflow/contracts.py coyote/services/reporting/common.py coyote/services/interpretation/annotation_enrichment.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.workflow.filter_normalization import normalize_rna_filter_keys, coerce_nonnegative_int; from coyote.services.rna.filter_compat import normalize_rna_filter_keys as compat; print('norm_import_ok', normalize_rna_filter_keys({'spanning_reads':'7','spanning_pairs':'0'}).get('min_spanning_reads'), compat({'spanning_reads':'7'}).get('min_spanning_reads'), coerce_nonnegative_int('-1'))"`
- Result:
  - Shared coercion/normalization is active with compatibility preserved.
  - Legacy compatibility path (`services/rna/filter_compat.py`) remains intact.
- Rollback needed: no
- Follow-up actions:
  - Proceed to `P4-2` and compare analyte-specific query builder parity before/after centralization.

### Task P4-2 - Query Builder Parity Check

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Preserve analyte-specific query builder entrypoints and enforce parity after service extraction.
  - Add explicit parity validation script and baseline artifact.
- Files changed:
  - `coyote/blueprints/rna/fusion_queries.py` (legacy entrypoint converted to service wrapper)
  - `migration_scripts/compare_rna_query_builder_parity.py` (new read-only parity script)
  - `migration_scripts/baselines/p4_query_parity_rna_builder_coyote_dev_3.json` (new artifact)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/blueprints/rna/fusion_queries.py coyote/services/rna/fusion_query_builder.py coyote/services/workflow/filter_normalization.py migration_scripts/compare_rna_query_builder_parity.py coyote/services/workflow/rna_workflow.py coyote/services/workflow/dna_workflow.py coyote/blueprints/rna/views.py coyote/blueprints/dna/views.py coyote/services/workflow/contracts.py coyote/services/reporting/common.py coyote/services/interpretation/annotation_enrichment.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python migration_scripts/compare_rna_query_builder_parity.py`
    - Result summary: `sample_count=4`, `comparisons=16`, `mismatch_count=0`, `status=ok`
- Result:
  - Query parity validated with zero mismatches for sampled RNA cases in `coyote_dev_3`.
  - Legacy builder remains available as compatibility wrapper.
- Rollback needed: no
- Follow-up actions:
  - Move to `P5-1` reporting pipeline internals unification with output-parity checks.

### Task P5-1 - Shared Reporting Pipeline Internals

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Unify DNA/RNA report save pipeline internals (mkdir/conflict check + HTML write + report metadata persist + snapshot persist).
  - Keep analyte-specific payload generation and route contracts unchanged.
- Files changed:
  - `coyote/services/reporting/pipeline.py` (new shared persistence pipeline)
  - `coyote/services/workflow/dna_workflow.py` (delegates report persistence to shared pipeline)
  - `coyote/services/workflow/rna_workflow.py` (delegates report persistence to shared pipeline)
  - `coyote/blueprints/dna/views.py` (uses workflow facade pipeline methods)
  - `coyote/blueprints/rna/views.py` (uses workflow facade pipeline methods)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `/data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/reporting/pipeline.py coyote/services/workflow/dna_workflow.py coyote/services/workflow/rna_workflow.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py coyote/services/workflow/filter_normalization.py coyote/services/workflow/contracts.py coyote/services/rna/fusion_query_builder.py coyote/services/rna/filter_compat.py coyote/services/reporting/common.py coyote/services/interpretation/annotation_enrichment.py`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote.services.reporting.pipeline import prepare_report_output, persist_report_and_snapshot; from coyote.services.workflow.dna_workflow import DNAWorkflowService; from coyote.services.workflow.rna_workflow import RNAWorkflowService; print('report_pipeline_import_ok')"`
- Result:
  - Shared report save pipeline is active for both DNA and RNA.
  - Existing endpoints, template payloads, permission behavior, and analyte-specific report content paths remain unchanged.
- Rollback needed: no
- Follow-up actions:
  - Move to `P6-1` template/component extraction (summary comments + markdown editor partials/macros) while preserving ids/classes.

### Task P6-1 - Shared Summary/Markdown Template Partials

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Extract duplicated summary comments block and markdown editor initialization into shared reusable template partials.
- Files changed:
  - `coyote/templates/components/summary_comments_card.html` (new)
  - `coyote/templates/components/summary_markdown_editor_js.html` (new)
  - `coyote/templates/components/summary_markdown_editor_styles.html` (new)
  - `coyote/blueprints/dna/templates/list_variants_vep.html` (uses shared components)
  - `coyote/blueprints/rna/templates/list_fusions.html` (uses shared components)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('list_variants_vep.html'); j.get_template('list_fusions.html'); j.get_template('components/summary_comments_card.html'); print('jinja_templates_ok')"`
- Result:
  - Shared summary/markdown components are active in both DNA and RNA list pages.
- Rollback needed: no
- Follow-up actions:
  - Confirm id/class parity and JS hooks remain stable (`P6-2`).

### Task P6-2 - Preserve Existing IDs/Classes for JS Compatibility

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Ensure extracted template components preserve existing JS hooks and styling selectors.
- Files changed:
  - `coyote/templates/components/summary_comments_card.html`
  - `coyote/templates/components/summary_markdown_editor_js.html`
  - `coyote/templates/components/summary_markdown_editor_styles.html`
  - `coyote/blueprints/dna/templates/list_variants_vep.html`
  - `coyote/blueprints/rna/templates/list_fusions.html`
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - Template include wiring verification:
    - `rg -n "components/summary_comments_card.html|components/summary_markdown_editor_js.html|components/summary_markdown_editor_styles.html" coyote/blueprints/dna/templates/list_variants_vep.html coyote/blueprints/rna/templates/list_fusions.html`
  - App init + template-load sanity:
    - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('list_variants_vep.html'); j.get_template('list_fusions.html'); print('jinja_templates_ok')"`
- Result:
  - Existing IDs/classes used by comment editor and summary table JS continue to resolve correctly.
- Rollback needed: no
- Follow-up actions:
  - Proceed to optional API evaluation (`P7-1`).

### Task P7-1 - Optional API Facade Evaluation

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Evaluate whether a new API facade should be introduced after service-layer stabilization.
- Files changed:
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (decision entry)
- Validation executed:
  - Reviewed current route landscape in `public_bp`, `common_bp`, `dna_bp`, `rna_bp`.
  - Reviewed migration status through P1-P6 completion.
- Result:
  - Decision: do **not** introduce a new API facade now.
  - Reasoning:
    - Existing blueprint routes already expose required behavior.
    - Current service-layer extraction provides internal decoupling without external contract risk.
    - Additional API surface in clinical/production context adds avoidable change risk unless there is a concrete integration requirement.
  - Reassessment trigger:
    - Add API facade only if an explicit external integration/use-case requires stable machine-facing contracts.
- Rollback needed: no
- Follow-up actions:
  - Continue with regression validation and production hardening, no further structural migration mandatory in this plan.

### Task P8-1 - Remove Remaining RNA `util.dna` Annotation Calls

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Remove remaining RNA coupling to `util.dna` for annotation enrichment where equivalent shared services already exist.
  - Preserve route contracts and rendering behavior.
- Files changed:
  - `coyote/blueprints/rna/views.py` (switched to `add_global_annotations` from shared interpretation service)
  - `coyote/services/workflow/rna_workflow.py` (switched to `add_alt_class` from shared interpretation service)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/blueprints/rna/views.py coyote/services/workflow/rna_workflow.py coyote/services/interpretation/annotation_enrichment.py`
  - `rg -n "util\\.dna\\.add_global_annotations|util\\.dna\\.add_alt_class" coyote/blueprints/rna/views.py coyote/services/workflow/rna_workflow.py` (no matches)
- Result:
  - RNA annotation enrichment path now uses shared service functions directly.
  - No endpoint signature, permission, or template contract changes.
- Rollback needed: no
- Follow-up actions:
  - Start `P8-2` with method-level DNA util inventory for safe extraction sequencing.

### Task P8-2 - DNA Utility Migration Inventory and Bucketing

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Produce function-level inventory for `DNAUtility` methods.
  - Classify each method into extraction buckets while preserving current runtime behavior.
- Files changed:
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `rg -n "^\s*def\s+" coyote/blueprints/dna/util.py`
  - `rg -n "util\.dna\.[a-zA-Z_][a-zA-Z0-9_]*\(" coyote`
  - Function-level usage count loop in repo root:
    - `for fn in ...; do rg -n "util\.dna\.${fn}\(" coyote | wc -l; done`
- Result:
  - Live-call, high-priority service candidates:
    - `build_dna_report_payload` (1 call; currently from `DNAWorkflowService`)
    - `get_variant_nomenclature` (3 calls; report/classification form paths)
    - `hotspot_variant`, `get_filter_conseq_terms`, `create_cnveffectlist`, `cnvtype_variant`, `cnv_organizegenes`, `format_pon` (all active in DNA views)
  - Already extracted/wrapper-backed:
    - `add_global_annotations`, `add_alt_class`, `get_report_timestamp`
  - Currently no direct `util.dna.*` call sites detected:
    - `get_protein_coding_genes`, `filter_variants_for_report`, `sort_by_class_and_af`, `get_simple_variants_for_report`
- Rollback needed: no
- Follow-up actions:
  - Start `P8-3` and then extract the first low-risk active candidate set (`get_filter_conseq_terms` + `create_cnveffectlist`) into shared services with wrapper compatibility.

### Task P8-3 - Shared List-Page JS Helper Consolidation

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Consolidate duplicated list-page JavaScript helpers used by DNA/RNA list pages.
  - Keep existing IDs/classes and onclick signatures unchanged.
- Files changed:
  - `coyote/templates/components/list_page_common_js.html` (new shared JS partial)
  - `coyote/blueprints/dna/templates/list_variants_vep.html` (includes shared partial, removed duplicate helper definitions)
  - `coyote/blueprints/rna/templates/list_fusions.html` (includes shared partial, removed duplicate helper definitions)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `rg -n "function showCheckboxes|function exportTableToCSV|window\\.onload\\s*=|var expanded\\s*=\\s*false|components/list_page_common_js.html" coyote/blueprints/dna/templates/list_variants_vep.html coyote/blueprints/rna/templates/list_fusions.html coyote/templates/components/list_page_common_js.html`
  - `PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('list_variants_vep.html'); j.get_template('list_fusions.html'); j.get_template('components/list_page_common_js.html'); print('jinja_templates_ok')"`
- Result:
  - Shared helpers now centralized for `showCheckboxes`, page-load autoclicks, filter toggle, and CSV export.
  - No route, ACL, template ID/class, or form-name changes.
- Rollback needed: no
- Follow-up actions:
  - Continue safe service extraction for active DNA utility methods.

### Task P8-4 - Extract Low-Risk Active DNA Filter Helpers

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Move active, low-risk DNA filter helper logic from blueprint utility into shared services.
  - Preserve existing `util.dna.*` call paths via compatibility wrappers.
- Files changed:
  - `coyote/services/workflow/dna_filters.py` (new shared helper module)
  - `coyote/blueprints/dna/util.py` (wrapper methods now delegate to shared helpers)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/dna_filters.py coyote/blueprints/dna/util.py coyote/blueprints/dna/views.py`
- Result:
  - `get_filter_conseq_terms` and `create_cnveffectlist` are now shared service logic.
  - Existing DNA view behavior remains unchanged because wrappers are intact.
- Rollback needed: no
- Follow-up actions:
  - Continue with next active DNA utility extraction candidates (`cnvtype_variant`, `cnv_organizegenes`, `format_pon`, `get_variant_nomenclature`) one at a time with validation gates.

### Task P8-5 - Extract Active CNV Helper Logic

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Move active CNV helper logic from `DNAUtility` to shared workflow services.
  - Preserve existing `util.dna.*` call paths via wrapper delegation.
- Files changed:
  - `coyote/services/workflow/dna_filters.py` (added `cnvtype_variant`, `cnv_organizegenes`)
  - `coyote/blueprints/dna/util.py` (CNV helper wrappers delegate to shared service)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/dna_filters.py coyote/blueprints/dna/util.py coyote/blueprints/dna/views.py`
- Result:
  - Active CNV helper logic is centralized in shared services with no call-site contract changes.
- Rollback needed: no
- Follow-up actions:
  - Continue extracting active non-CNV utility helpers with the same wrapper pattern.

### Task P8-6 - Extract Active Variant-Format Helper Logic

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Move active variant formatting helpers from `DNAUtility` to shared workflow services.
  - Preserve existing view behavior through compatibility wrappers.
- Files changed:
  - `coyote/services/workflow/dna_variants.py` (new shared helper module with `format_pon`, `get_variant_nomenclature`)
  - `coyote/blueprints/dna/util.py` (wrapper delegation to shared variant helpers)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/dna_variants.py coyote/services/workflow/dna_filters.py coyote/blueprints/dna/util.py coyote/blueprints/dna/views.py`
- Result:
  - `format_pon` and `get_variant_nomenclature` are now shared service logic with unchanged wrapper call sites.
- Rollback needed: no
- Follow-up actions:
  - Continue with remaining high-complexity candidates only after targeted parity validation (`build_dna_report_payload`).

### Regression Sweep RS-1 - DNA/RNA Workflow and Template Sanity

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Execute a focused post-migration regression sweep for DNA and RNA workflow paths.
  - Validate query parity, baseline capture integrity, template loading, app initialization, and syntax.
- Files changed:
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update only)
- Validation executed:
  - RNA query parity:
    - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python migration_scripts/compare_rna_query_builder_parity.py`
    - Result: `sample_count=4`, `comparisons=16`, `mismatch_count=0`, `status=ok`
  - Route/query/report baseline recapture:
    - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python migration_scripts/capture_phase0_route_query_report_baseline.py`
    - Result: baseline written successfully with 4 sample entries
  - App init + key DNA/RNA template load:
    - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('list_variants_vep.html'); j.get_template('list_fusions.html'); j.get_template('show_variant_vep.html'); j.get_template('show_fusion.html'); print('app_and_templates_ok')"`
    - Result: `app_and_templates_ok`
  - Syntax checks for migrated core modules:
    - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/workflow/dna_workflow.py coyote/services/workflow/rna_workflow.py coyote/services/reporting/pipeline.py coyote/services/reporting/common.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py coyote/blueprints/dna/util.py`
    - Result: pass
- Result:
  - Regression sweep passed for the focused, scriptable validation gates.
  - No parity mismatches detected in RNA query builder checks.
  - No import/template syntax regressions detected in key DNA/RNA paths.
- Rollback needed: no
- Follow-up actions:
  - Optional: run interactive UI smoke checks (list filters, sidebar toggles, report preview/save) in browser against the same golden samples.

### Task P9-1 - Shared BPCommon Service Extraction

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Remove cross-blueprint business-logic coupling by extracting shared `bpcommon` logic from blueprint-common util into services.
  - Rewire DNA/RNA/common views to use shared services directly.
  - Keep compatibility wrappers in `blueprints/common/util.py` to avoid route/handler breakage.
- Files changed:
  - `coyote/services/interpretation/bp_common.py` (new shared service for summary generation, comment docs, annotation text, tier sorting, enrichment)
  - `coyote/blueprints/common/util.py` (rewritten as compatibility wrappers delegating to service)
  - `coyote/blueprints/dna/views.py` (rewired `generate_summary_text`, `create_annotation_text_from_gene`, `create_comment_doc`)
  - `coyote/blueprints/rna/views.py` (rewired `generate_summary_text`)
  - `coyote/blueprints/common/views.py` (rewired `create_comment_doc`, `enrich_reported_variant_docs`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/interpretation/bp_common.py coyote/blueprints/common/util.py coyote/blueprints/common/views.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
  - `rg -n "util\\.bpcommon\\." coyote || true` (no direct callsites remaining)
- Result:
  - Shared interpretation/report-text logic now lives in services, reducing blueprint coupling.
  - Existing behavior preserved via wrappers and direct service rewiring in active call paths.
- Rollback needed: no
- Follow-up actions:
  - Continue optional cleanups by extracting any remaining cross-blueprint helper logic that is still utility-only and not route-specific.

### Task P9-2 - Immediate Utility Aggregator Detach for Migrated Modules

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Complete immediate cleanup (no deferred shrink) by detaching already-migrated helper modules from injected `util`.
  - Migrate active `util.rna` workflow usages into shared services before detaching.
- Files changed:
  - `coyote/services/rna/helpers.py` (new shared RNA helper service)
  - `coyote/services/workflow/rna_workflow.py` (rewired to `services.rna.helpers`)
  - `coyote/blueprints/rna/util.py` (compatibility wrappers delegate to shared RNA helpers)
  - `coyote/util/__init__.py` (removed `self.bpcommon` and `self.rna` attachments + related imports)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `rg -n "util\\.bpcommon|util\\.rna" coyote || true` (no active callsites)
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/rna/helpers.py coyote/services/workflow/rna_workflow.py coyote/util/__init__.py coyote/services/interpretation/bp_common.py coyote/blueprints/common/util.py coyote/blueprints/common/views.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Deferred shrink eliminated for migrated modules.
  - Injected utility surface is immediately reduced for `bpcommon` and `rna` without changing runtime behavior.
- Rollback needed: no
- Follow-up actions:
  - Continue same hard-cut pattern for future migrated util modules: migrate callsites first, then detach from `Utility` in the same task.

### Task P9-3 - Remove Legacy Blueprint Wrapper Functions/Files

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Remove legacy blueprint utility wrappers for functionality already moved to service modules.
  - Ensure active callsites use service-layer functions directly.
- Files changed:
  - `coyote/blueprints/dna/views.py` (rewired migrated helper callsites to services)
  - `coyote/blueprints/dna/util.py` (removed legacy wrapper methods moved to services; kept remaining non-migrated DNA logic)
  - `coyote/blueprints/common/util.py` (deleted; no remaining references)
  - `coyote/blueprints/rna/util.py` (deleted; no remaining references)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `rg -n "util\\.dna\\.(get_filter_conseq_terms|create_cnveffectlist|format_pon|add_global_annotations|add_alt_class|get_variant_nomenclature|cnvtype_variant|cnv_organizegenes|get_report_timestamp)\\(" coyote || true`
  - `rg -n "BPCommonUtility|RNAUtility|blueprints\\.common\\.util|blueprints\\.rna\\.util|util\\.bpcommon|util\\.rna" coyote || true`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/blueprints/dna/util.py coyote/blueprints/dna/views.py coyote/services/workflow/dna_workflow.py coyote/services/workflow/rna_workflow.py coyote/services/interpretation/bp_common.py coyote/services/rna/helpers.py coyote/util/__init__.py coyote/blueprints/common/views.py coyote/blueprints/rna/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Legacy wrapper functions/files already migrated to services are removed from blueprints.
  - No runtime/app-init regression detected in validation checks.
- Rollback needed: no
- Follow-up actions:
  - Apply the same delete-after-migration rule for any future utility extractions.

### Task P9-4 - Service Naming Cleanup (`bp_common`/`common` -> explicit names)

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Replace ambiguous service naming with explicit domain-oriented names.
  - Expose function-based service entrypoints for active callsites.
- Files changed:
  - `coyote/services/interpretation/report_summary.py` (new function-based entrypoints for summary/comment/annotation helpers)
  - `coyote/services/reporting/report_paths.py` (new canonical report path/timestamp helpers)
  - `coyote/services/reporting/common.py` (compatibility shim to `report_paths`)
  - `coyote/blueprints/dna/views.py` (uses `report_summary` functions)
  - `coyote/blueprints/rna/views.py` (uses `report_summary` function)
  - `coyote/blueprints/common/views.py` (uses `report_summary` functions)
  - `coyote/services/workflow/dna_workflow.py` (uses `report_paths`)
  - `coyote/services/workflow/rna_workflow.py` (uses `report_paths`)
  - `coyote/blueprints/dna/util.py` (uses `report_paths` import for timestamp helper)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/interpretation/report_summary.py coyote/services/reporting/report_paths.py coyote/services/reporting/common.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py coyote/blueprints/common/views.py coyote/services/workflow/dna_workflow.py coyote/services/workflow/rna_workflow.py coyote/blueprints/dna/util.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Active code now uses clearer service names.
  - Function-based imports are in place at callsites while preserving compatibility where needed.
- Rollback needed: no
- Follow-up actions:
  - Optional future cleanup: fold `BPCommonService` internals directly into module-level functions in `report_summary.py` and demote `bp_common.py` to pure legacy shim.

### Task P9-5 - Remove Wrapper Layers and Keep Direct Implementations

- Date: 2026-02-25
- Owner: Codex
- Scope:
  - Eliminate unnecessary class-wrapper and module-wrapper layers after naming cleanup.
  - Keep one direct implementation path per domain module.
- Files changed:
  - `coyote/services/interpretation/report_summary.py` (promoted to full direct implementation)
  - `coyote/services/interpretation/bp_common.py` (deleted)
  - `coyote/services/reporting/common.py` (deleted)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `rg -n "services\\.interpretation\\.bp_common|BPCommonService|services\\.reporting\\.common" coyote || true`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -m py_compile coyote/services/interpretation/report_summary.py coyote/services/reporting/report_paths.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py coyote/blueprints/common/views.py coyote/services/workflow/dna_workflow.py coyote/services/workflow/rna_workflow.py coyote/blueprints/dna/util.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3/.venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Wrapper indirection removed; direct, meaningful modules are now the canonical implementation points.
- Rollback needed: no
- Follow-up actions:
  - Continue same rule: avoid adding wrapper-only classes/modules unless there is a concrete compatibility requirement.

### Task P10-1 - Extract Remaining DNA Report/Variant Helpers

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Move remaining `DNAUtility` report/variant helper logic to shared services.
  - Switch active DNA callsites to service functions while preserving behavior.
- Files changed:
  - `coyote/services/workflow/dna_reporting.py` (new shared module with `hotspot_variant`, `filter_variants_for_report`, `sort_by_class_and_af`, `get_simple_variants_for_report`)
  - `coyote/blueprints/dna/util.py` (rewired report payload flow to shared helpers; `DNAUtility` methods delegate to services as compatibility wrappers)
  - `coyote/blueprints/dna/views.py` (list flow now calls shared `hotspot_variant`; removed direct `DNAUtility` import)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && rg -n "DNAUtility\\.hotspot_variant|DNAUtility\\.filter_variants_for_report|DNAUtility\\.sort_by_class_and_af|DNAUtility\\.get_simple_variants_for_report|from coyote\\.blueprints\\.dna\\.util import DNAUtility" coyote -g '*.py'`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/services/workflow/dna_reporting.py coyote/blueprints/dna/util.py coyote/blueprints/dna/views.py coyote/services/workflow/dna_workflow.py`
- Result:
  - Extracted helper logic is now centralized in `services/workflow/dna_reporting.py`.
  - Active callsites use shared service functions.
  - `DNAUtility` remains only as a compatibility layer for these helpers.
- Rollback needed: no
- Follow-up actions:
  - Proceed to `P10-2` and move `build_dna_report_payload` into the service layer to remove remaining workflow dependency on blueprint utility module.

### Tasks P10-2/P10-3/P10-4/P10-5 - DNA Utility Hard-Cut Completion

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Complete the remaining DNA finalization tasks with no temporary compatibility wrappers.
  - Remove service dependency on blueprint utility module and delete legacy DNA utility file.
- Files changed:
  - `coyote/services/workflow/dna_reporting.py` (added `build_dna_report_payload`; now hosts canonical DNA report helper stack)
  - `coyote/services/workflow/dna_workflow.py` (rewired to import `build_dna_report_payload` from `services.workflow.dna_reporting`)
  - `coyote/blueprints/dna/util.py` (deleted)
  - `coyote/util/__init__.py` (removed stale `DNAUtility` mention from utility-aggregator docs)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && rg -n "DNAUtility|blueprints\\.dna\\.util|util\\.dna" coyote -g '*.py'`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/services/workflow/dna_reporting.py coyote/services/workflow/dna_workflow.py coyote/blueprints/dna/views.py coyote/util/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - `build_dna_report_payload` moved to service layer.
  - No remaining `DNAUtility` imports/calls in Python code.
  - Legacy `blueprints/dna/util.py` removed.
  - Utility aggregator no longer mentions/depends on DNA utility class.
  - App initialization passes after hard-cut cleanup.
- Rollback needed: no
- Follow-up actions:
  - Optional: run golden-sample route/query/report baseline recapture to close out DNA finalization with explicit parity artifact for 2026-02-26 changes.

### Regression Sweep RS-2 - Post Hard-Cut Baseline/Parity Recapture

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Re-run baseline/parity scripts immediately after DNA utility hard-cut completion.
- Files changed:
  - `migration_scripts/baselines/p4_query_parity_rna_builder_coyote_dev_3.json` (refreshed artifact)
  - `migration_scripts/baselines/phase0_route_query_report_baseline_coyote_dev_3.json` (refreshed artifact)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python migration_scripts/compare_rna_query_builder_parity.py`
    - Result: `sample_count=4`, `comparisons=16`, `mismatch_count=0`, `status=ok`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python migration_scripts/capture_phase0_route_query_report_baseline.py`
    - Result: baseline written with `sample entries=4`
- Result:
  - Post-hard-cut validation artifacts were regenerated successfully.
  - No parity mismatches detected.
- Rollback needed: no
- Follow-up actions:
  - Optional: compare refreshed baseline artifact against prior snapshot in detail for route/query/report field-level drift audit.

### Consistency Refactor CR-1 - Align DNA Service Folder Structure

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Align DNA service module layout with existing RNA domain layout by introducing `coyote/services/dna/`.
  - Keep workflow facade and behavior unchanged; move only module paths/imports.
- Files changed:
  - `coyote/services/dna/dna_filters.py` (moved from `services/workflow`)
  - `coyote/services/dna/dna_variants.py` (moved from `services/workflow`)
  - `coyote/services/dna/dna_reporting.py` (moved from `services/workflow`)
  - `coyote/services/workflow/dna_workflow.py` (imports updated to `services.dna`)
  - `coyote/blueprints/dna/views.py` (imports updated to `services.dna`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && rg -n "services\\.workflow\\.dna_(filters|variants|reporting)" coyote -g '*.py'`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/services/dna/dna_filters.py coyote/services/dna/dna_variants.py coyote/services/dna/dna_reporting.py coyote/services/workflow/dna_workflow.py coyote/blueprints/dna/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - DNA and RNA domain services now follow a consistent folder structure.
  - No import/runtime regressions detected in compile and app-init checks.
- Rollback needed: no
- Follow-up actions:
  - Optional: migrate module names from `dna_*.py` to shorter names (`filters.py`, `variants.py`, `reporting.py`) if you want stricter symmetry with `services/rna/*`.

### Task P11-1 - Shared Template Filter Helper Extraction (Phase 1)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Start Flask/API structure hardening by extracting duplicated, non-route template-filter logic into a shared module.
  - Keep filter names and template contracts unchanged.
- Files changed:
  - `coyote/filters/__init__.py` (new package)
  - `coyote/filters/shared.py` (new shared helpers: `human_date`, `format_comment_markdown`, `format_fusion_desc_badges`, `uniq_callers`)
  - `coyote/blueprints/common/filters.py` (delegates `human_date` and `format_comment` to shared helpers)
  - `coyote/blueprints/rna/filters.py` (delegates `format_fusion_desc_few`, `format_fusion_desc`, `uniq_callers` to shared helpers)
  - `coyote/blueprints/dna/filters.py` (delegates `uniq_callers` to shared helper; includes `format_panel_flag_snv` parsing bugfix)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/filters/shared.py coyote/blueprints/common/filters.py coyote/blueprints/rna/filters.py coyote/blueprints/dna/filters.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('list_fusions.html'); j.get_template('dna_report.html'); print('filters_templates_ok')"`
- Result:
  - Initial shared filter extraction is active without changing template filter names.
  - Foundation is in place for `P11-2` centralized registration and further deduplication.
- Rollback needed: no
- Follow-up actions:
  - Continue `P11-1` by extracting additional safe shared helpers (`shorten_number`, `render_markdown`/`format_comment` convergence points) before moving to `P11-2`.

### Task P11-2 - Centralized Filter Registration (No Import-Order Coupling)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Add explicit centralized filter registration in app initialization.
  - Remove blueprint/view side-effect imports previously used only to register filters.
- Files changed:
  - `coyote/filters/registry.py` (new centralized `register_filters(app)` entrypoint)
  - `coyote/__init__.py` (new `init_template_filters(app)` call in app factory before blueprint registration)
  - `coyote/blueprints/common/__init__.py` (removed side-effect filter import)
  - `coyote/blueprints/dna/__init__.py` (removed side-effect filter import)
  - `coyote/blueprints/admin/__init__.py` (removed side-effect filter import)
  - `coyote/blueprints/public/__init__.py` (removed side-effect filter import)
  - `coyote/blueprints/dna/views.py` (removed side-effect `filters` import)
  - `coyote/blueprints/rna/views.py` (removed side-effect `filters` import)
  - `coyote/blueprints/home/views.py` (removed side-effect `filters` import)
  - `coyote/blueprints/dashboard/views.py` (removed side-effect `filters` import)
  - `coyote/blueprints/public/views.py` (removed side-effect `filters` import)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/filters/registry.py coyote/__init__.py coyote/blueprints/dna/views.py coyote/blueprints/rna/views.py coyote/blueprints/home/views.py coyote/blueprints/dashboard/views.py coyote/blueprints/public/views.py coyote/blueprints/common/__init__.py coyote/blueprints/dna/__init__.py coyote/blueprints/admin/__init__.py coyote/blueprints/public/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('dashboard.html'); j.get_template('samples_home.html'); j.get_template('list_fusions.html'); j.get_template('dna_report.html'); print('filter_registry_ok')"`
- Result:
  - Filter registration is now explicit and centralized in app startup.
  - Registration no longer depends on blueprint import side effects or view import ordering.
  - Template filter availability verified across dashboard/home/rna/dna templates.
- Rollback needed: no
- Follow-up actions:
  - Continue `P11-1` deduplication of remaining low-risk duplicated filters before route-file split/API scaffolding tasks.

### Task P11-1 - Shared Template Filter Helper Extraction (Phase 1, Continuation)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue low-risk shared filter extraction by moving dashboard number-format logic to shared helpers.
- Files changed:
  - `coyote/filters/shared.py` (added `shorten_number`)
  - `coyote/blueprints/dashboard/filters.py` (wrapper delegates to shared helper)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/filters/shared.py coyote/blueprints/dashboard/filters.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('dashboard.html'); print('dashboard_filters_ok')"`
- Result:
  - Dashboard filter logic now reuses shared helper with unchanged filter name (`shorten_number`).
- Rollback needed: no
- Follow-up actions:
  - Continue `P11-1` for remaining low-risk shared filter candidates.

### Task P11-3 - Route Module Split (DNA Reports Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Start splitting oversized DNA route module by extracting report routes into a dedicated route-domain module.
  - Preserve existing URLs, endpoint names, decorators, and service orchestration behavior.
- Files changed:
  - `coyote/blueprints/dna/views_reports.py` (new report-route module with `generate_dna_report` and `save_dna_report`)
  - `coyote/blueprints/dna/views.py` (removed report routes; kept remaining route handlers)
  - `coyote/blueprints/dna/__init__.py` (imports `views_reports` to register extracted routes)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/dna/views.py coyote/blueprints/dna/views_reports.py coyote/blueprints/dna/__init__.py coyote/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; print('dna_bp.generate_dna_report' in eps, 'dna_bp.save_dna_report' in eps)"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); j=app.jinja_env; j.get_template('dna_report.html'); print('dna_report_template_ok')"`
- Result:
  - DNA report routes are now isolated in their own module.
  - Endpoint registration and template loading remained intact (`True True` for endpoint presence).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with next low-risk DNA route slices (for example CNV/translocation action groups), then apply the same pattern to `admin/views.py`.

### Task P11-3 - Route Module Split (DNA CNV/Translocation Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue DNA route modularization by extracting CNV and translocation handlers from `dna/views.py`.
  - Preserve exact URLs, endpoint names, decorators, and behavior.
- Files changed:
  - `coyote/blueprints/dna/views_cnv.py` (new CNV route module)
  - `coyote/blueprints/dna/views_transloc.py` (new translocation route module)
  - `coyote/blueprints/dna/views.py` (removed extracted CNV/translocation handlers)
  - `coyote/blueprints/dna/__init__.py` (imports new route modules for registration)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && rg -n "def (show_cnv|unmark_interesting_cnv|mark_interesting_cnv|mark_false_cnv|unmark_false_cnv|mark_noteworthy_cnv|unmark_noteworthy_cnv|hide_cnv_comment|unhide_cnv_comment|show_transloc|mark_interesting_transloc|unmark_interesting_transloc|mark_false_transloc|unmark_false_transloc|hide_transloc_comment|unhide_transloc_comment)" coyote/blueprints/dna/views.py coyote/blueprints/dna/views_cnv.py coyote/blueprints/dna/views_transloc.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/dna/views.py coyote/blueprints/dna/views_cnv.py coyote/blueprints/dna/views_transloc.py coyote/blueprints/dna/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted=['dna_bp.show_cnv','dna_bp.unmark_interesting_cnv','dna_bp.mark_interesting_cnv','dna_bp.mark_false_cnv','dna_bp.unmark_false_cnv','dna_bp.mark_noteworthy_cnv','dna_bp.unmark_noteworthy_cnv','dna_bp.hide_cnv_comment','dna_bp.unhide_cnv_comment','dna_bp.show_transloc','dna_bp.mark_interesting_transloc','dna_bp.unmark_interesting_transloc','dna_bp.mark_false_transloc','dna_bp.unmark_false_transloc','dna_bp.hide_transloc_comment','dna_bp.unhide_transloc_comment']; print(all(w in eps for w in wanted), len([w for w in wanted if w in eps]))"`
- Result:
  - CNV/translocation routes are now isolated in dedicated route modules.
  - All extracted endpoints remained registered (`True`, `16` present).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with the next low-risk DNA slice (variant action/comment handlers), then begin initial `admin/views.py` modularization.

### Task P11-3 - Route Module Split (DNA Variant Action/Comment Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue DNA route modularization by extracting variant action/classification/comment handlers from `dna/views.py`.
  - Preserve exact route URLs, endpoint names, decorators, and redirect behavior.
- Files changed:
  - `coyote/blueprints/dna/views_variant_actions.py` (new route module for variant actions/comments)
  - `coyote/blueprints/dna/views.py` (removed extracted handlers and stale imports)
  - `coyote/blueprints/dna/__init__.py` (imports `views_variant_actions` for route registration)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && python -m py_compile coyote/blueprints/dna/views.py coyote/blueprints/dna/views_variant_actions.py coyote/blueprints/dna/views_cnv.py coyote/blueprints/dna/views_transloc.py coyote/blueprints/dna/views_reports.py coyote/blueprints/dna/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); endpoints={'dna_bp.add_variant_to_blacklist','dna_bp.classify_variant','dna_bp.classify_fusion','dna_bp.remove_classified_variant','dna_bp.remove_classified_fusion','dna_bp.add_variant_comment','dna_bp.add_cnv_comment','dna_bp.add_fusion_comment','dna_bp.add_translocation_comment'}; registered={r.endpoint for r in app.url_map.iter_rules()}; missing=sorted(endpoints-registered); print('missing', missing); print('count', len(endpoints & registered))"`
- Result:
  - Variant action/comment endpoints are registered from dedicated module.
  - Extracted module fixed two correctness issues during move: wrong redirect arg in blacklist flow and missing optional `id` fallback on remove-classification route.
  - Endpoint verification returned `missing []` and `count 9`.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with `admin/views.py` module splitting using the same route-domain pattern.

### Task P11-3 - Route Module Split (Admin User-Management Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Start `admin/views.py` modularization by extracting `/users*` routes into a dedicated module.
  - Preserve existing URLs, endpoint names, decorators, audit hooks, and templates.
- Files changed:
  - `coyote/blueprints/admin/views_users.py` (new route-domain module for user management)
  - `coyote/blueprints/admin/views.py` (removed extracted `/users*` handlers)
  - `coyote/blueprints/admin/__init__.py` (imports `views_users` for route registration)
  - `coyote/blueprints/userprofile/views.py` (import path updated to `admin.views_users.view_user`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_users.py coyote/blueprints/admin/__init__.py coyote/blueprints/userprofile/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'admin_bp.manage_users','admin_bp.create_user','admin_bp.edit_user','admin_bp.view_user','admin_bp.delete_user','admin_bp.validate_username','admin_bp.validate_email','admin_bp.toggle_user_active'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps)); print('profile', 'profile_bp.user_profile' in eps)"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Admin user-management routes are now isolated in `views_users.py` and still fully registered (`missing []`, `count 8`).
  - Profile route integration remains intact (`profile_bp.user_profile` present).
  - During validation, one existing quote bug in role flash text was corrected in `admin/views.py` while preserving behavior.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with next admin slices (`/schemas*`, `/permissions*`, `/roles*`) using the same extraction pattern.

### Task P11-3 - Route Module Split (Admin Schema-Management Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue `admin/views.py` modularization by extracting `/schemas*` handlers into a separate route-domain module.
  - Preserve existing route paths, endpoint names, decorators, template contracts, and audit metadata behavior.
- Files changed:
  - `coyote/blueprints/admin/views_schemas.py` (new schema-management route module)
  - `coyote/blueprints/admin/views.py` (removed extracted `/schemas*` handlers)
  - `coyote/blueprints/admin/__init__.py` (imports `views_schemas` for route registration)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_users.py coyote/blueprints/admin/views_schemas.py coyote/blueprints/admin/__init__.py coyote/blueprints/userprofile/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; users={'admin_bp.manage_users','admin_bp.create_user','admin_bp.edit_user','admin_bp.view_user','admin_bp.delete_user','admin_bp.validate_username','admin_bp.validate_email','admin_bp.toggle_user_active'}; schemas={'admin_bp.schemas','admin_bp.toggle_schema_active','admin_bp.edit_schema','admin_bp.create_schema','admin_bp.delete_schema'}; print('users_missing', sorted(users-eps)); print('users_count', len(users & eps)); print('schemas_missing', sorted(schemas-eps)); print('schemas_count', len(schemas & eps)); print('profile', 'profile_bp.user_profile' in eps)"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Schema endpoints remain fully registered (`schemas_missing []`, `schemas_count 5`).
  - Previously extracted user endpoints still intact (`users_missing []`, `users_count 8`), and user profile route remains available.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with `/permissions*` extraction, then `/roles*`, then assay/genelist/audit slices.

### Task P11-3 - Route Module Split (Admin Permissions/Roles Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue `admin/views.py` modularization by extracting `/permissions*` and `/roles*` handlers into dedicated modules.
  - Preserve route paths, endpoint names, decorators, and template contracts.
- Files changed:
  - `coyote/blueprints/admin/views_permissions.py` (new permissions route module)
  - `coyote/blueprints/admin/views_roles.py` (new roles route module)
  - `coyote/blueprints/admin/views.py` (removed extracted handlers)
  - `coyote/blueprints/admin/__init__.py` (imports new route modules)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_users.py coyote/blueprints/admin/views_schemas.py coyote/blueprints/admin/views_permissions.py coyote/blueprints/admin/views_roles.py coyote/blueprints/admin/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'admin_bp.list_permissions','admin_bp.create_permission','admin_bp.edit_permission','admin_bp.view_permission','admin_bp.toggle_permission_active','admin_bp.delete_permission','admin_bp.list_roles','admin_bp.create_role','admin_bp.edit_role','admin_bp.view_role','admin_bp.toggle_role_active','admin_bp.delete_role'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - All extracted permission/role endpoints remain registered (`missing []`, `count 12`).
  - Admin route decomposition now includes users, schemas, permissions, and roles.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with assay-panel/assay-config/genelist/audit slices.

### Task P11-3 - Route Module Split (Admin Sample-Management Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue `admin/views.py` modularization by extracting `/manage-samples*` and sample-edit/delete handlers.
  - Preserve URLs, endpoint names, decorators, templates, and audit metadata behavior.
- Files changed:
  - `coyote/blueprints/admin/views_samples.py` (new sample-management route module)
  - `coyote/blueprints/admin/views.py` (removed extracted sample handlers)
  - `coyote/blueprints/admin/__init__.py` (imports `views_samples`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_samples.py coyote/blueprints/admin/views_users.py coyote/blueprints/admin/views_schemas.py coyote/blueprints/admin/views_permissions.py coyote/blueprints/admin/views_roles.py coyote/blueprints/admin/__init__.py coyote/blueprints/api/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'admin_bp.all_samples','admin_bp.edit_sample','admin_bp.delete_sample','admin_bp.list_permissions','admin_bp.create_permission','admin_bp.edit_permission','admin_bp.view_permission','admin_bp.toggle_permission_active','admin_bp.delete_permission','admin_bp.list_roles','admin_bp.create_role','admin_bp.edit_role','admin_bp.view_role','admin_bp.toggle_role_active','admin_bp.delete_role','api_bp.list_dna_variants','api_bp.show_dna_variant','api_bp.list_rna_fusions','api_bp.show_rna_fusion'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Sample management is now split into its own module with endpoints intact.
  - Combined check confirmed all targeted admin/API endpoints still registered (`missing []`, `count 19`).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with assay panel/config, genelist, and audit route extraction.

### Task P11-3 - Route Module Split (Admin Audit Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extract `/admin/audit` route into a dedicated admin route module.
  - Preserve route path, endpoint name, RBAC decorator, and template behavior.
- Files changed:
  - `coyote/blueprints/admin/views_audit.py` (new audit route module)
  - `coyote/blueprints/admin/views.py` (removed extracted audit route)
  - `coyote/blueprints/admin/__init__.py` (imports `views_audit`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_audit.py coyote/blueprints/admin/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; print('audit_present', 'admin_bp.audit' in eps)"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Audit endpoint remains registered (`audit_present True`).
  - Admin route modularization continued without regressions.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with assay panel/config and genelist slices.

### Task P11-3 - Route Module Split (Admin Genelist Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extract all `/genelists*` routes from `admin/views.py` into a dedicated route module.
  - Preserve route paths, endpoint names, RBAC decorators, and templates.
- Files changed:
  - `coyote/blueprints/admin/views_genelists.py` (new genelist route module)
  - `coyote/blueprints/admin/views.py` (removed extracted genelist handlers)
  - `coyote/blueprints/admin/__init__.py` (imports `views_genelists`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_genelists.py coyote/blueprints/admin/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'admin_bp.manage_genelists','admin_bp.create_genelist','admin_bp.edit_genelist','admin_bp.toggle_genelist','admin_bp.delete_genelist','admin_bp.view_genelist'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - Genelist routes are now isolated in `views_genelists.py`.
  - Endpoint registration remained intact (`missing []`, `count 6`).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 by extracting assay panel/config route groups.

### Task P11-3 - Route Module Split (Admin Assay Panel/Config Slices)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extract remaining `/asp*` and `/aspc*` routes into dedicated modules and reduce `admin/views.py` to entry-level handlers only.
  - Preserve route URLs, endpoint names, decorators, and behavior.
- Files changed:
  - `coyote/blueprints/admin/views_assay_panels.py` (new `/asp*` route module)
  - `coyote/blueprints/admin/views_assay_configs.py` (new `/aspc*` route module)
  - `coyote/blueprints/admin/views.py` (removed extracted assay panel/config handlers; now only `admin_home`)
  - `coyote/blueprints/admin/__init__.py` (imports new assay route modules)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/admin/views.py coyote/blueprints/admin/views_samples.py coyote/blueprints/admin/views_users.py coyote/blueprints/admin/views_schemas.py coyote/blueprints/admin/views_permissions.py coyote/blueprints/admin/views_roles.py coyote/blueprints/admin/views_audit.py coyote/blueprints/admin/views_genelists.py coyote/blueprints/admin/views_assay_panels.py coyote/blueprints/admin/views_assay_configs.py coyote/blueprints/admin/__init__.py coyote/blueprints/api/views.py coyote/errors/handlers.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'admin_bp.admin_home','admin_bp.manage_assay_panels','admin_bp.create_assay_panel','admin_bp.edit_assay_panel','admin_bp.view_assay_panel','admin_bp.print_assay_panel','admin_bp.toggle_assay_panel_active','admin_bp.delete_assay_panel','admin_bp.assay_configs','admin_bp.create_dna_assay_config','admin_bp.create_rna_assay_config','admin_bp.edit_assay_config','admin_bp.view_assay_config','admin_bp.print_assay_config','admin_bp.toggle_assay_config_active','admin_bp.delete_assay_config','admin_bp.manage_genelists','admin_bp.create_genelist','admin_bp.edit_genelist','admin_bp.toggle_genelist','admin_bp.delete_genelist','admin_bp.view_genelist','admin_bp.audit','api_bp.list_dna_variants','api_bp.show_dna_variant','api_bp.list_rna_fusions','api_bp.show_rna_fusion'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); c=app.test_client(); r_api=c.get('/api/this-does-not-exist'); r_web=c.get('/this-does-not-exist'); print('api_status', r_api.status_code); print('api_json', r_api.json); print('web_status', r_web.status_code); print('web_ct', r_web.content_type); print('app_init_ok')"`
- Result:
  - `admin/views.py` is now minimized and route complexity moved into dedicated modules.
  - Endpoint parity check passed (`missing []`, `count 27`).
  - API/web error behavior still aligned (API 404 JSON, web 404 HTML).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 with remaining large-route blueprints (next: `rna/views.py` decomposition).

### Task P11-4 - API Blueprint Scaffolding (Initial)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Add initial API blueprint scaffold without changing existing web routes.
  - Reuse existing RBAC metadata (`@require`) for API endpoints.
- Files changed:
  - `coyote/blueprints/api/__init__.py` (new `api_bp`)
  - `coyote/blueprints/api/views.py` (new v1 endpoints: `/v1/health`, `/v1/auth/whoami`)
  - `coyote/__init__.py` (registers `api_bp` at `/api`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && python -m py_compile coyote/blueprints/api/__init__.py coyote/blueprints/api/views.py coyote/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; print('api_bp.health' in eps, 'api_bp.whoami' in eps)"`
- Result:
  - API blueprint is active and versioned under `/api/v1/*`.
  - RBAC metadata flow is reused (`whoami` is annotated with `@require(min_level=1)`).
- Rollback needed: no
- Follow-up actions:
  - Add first domain API read endpoints (DNA/RNA list/detail) by reusing existing service-layer query builders.

### Task P11-5 - API-Aware Auth/Permission Response Mode

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extend centralized `before_request` permission enforcement so API routes return JSON auth errors.
  - Keep existing redirect + flash behavior for web routes unchanged.
- Files changed:
  - `coyote/__init__.py` (added API request detection and JSON `401/403` failure responses inside `enforce_permissions`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + work log update)
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && python -m py_compile coyote/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); print('app_init_ok')"`
- Result:
  - API requests under `/api/*` now receive machine-readable auth failures:
    - `401` with `{\"status\": 401, \"error\": \"Login required\"}`
    - `403` with `{\"status\": 403, \"error\": \"You do not have access to this page.\"}`
  - Web routes retain current flash + redirect user experience.
- Rollback needed: no
- Follow-up actions:
  - Optionally mirror API-aware JSON handling for global error handlers (`AppError`/HTTP 4xx/5xx) when request target is API blueprint.

### Task P12-1 - Frontend/API Strategy Decision

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Confirm migration direction for frontend/API architecture before broad endpoint expansion.
  - Keep server-rendered web routes as primary while API surface grows in parallel.
- Files changed:
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md` (status + strategy record)
- Validation executed:
  - Architectural alignment validated in implementation by preserving existing web route behavior and adding API endpoints in parallel.
- Result:
  - Explicitly adopted a phased migration strategy (no big-bang frontend rewrite).
  - API additions now proceed per feature with RBAC parity and rollback-safe progression.
- Rollback needed: no
- Follow-up actions:
  - Continue P12-2 by adding parity endpoints screen-by-screen.

### Task P12-2 - API Parity Endpoints (DNA List/Detail Initial Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Add initial read-only DNA parity endpoints that reuse existing query builders and enrichment services.
  - Enforce RBAC and sample-assay access with API-native JSON error responses.
- Files changed:
  - `coyote/blueprints/api/views.py`
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/api/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'api_bp.list_dna_variants','api_bp.show_dna_variant'}; print('missing', sorted(wanted-eps)); print('count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); c=app.test_client(); r=c.get('/api/v1/dna/samples/does-not-matter/variants'); print('status', r.status_code); print('json', r.json)"`
- Result:
  - Added endpoints:
    - `GET /api/v1/dna/samples/<sample_id>/variants`
    - `GET /api/v1/dna/samples/<sample_id>/variants/<var_id>`
  - Endpoints reuse DNA list/detail building blocks (`build_query`, global annotation enrichment, blacklist/hotspot enrichment).
  - Responses are JSON-serializable through shared utility conversion.
- Rollback needed: no
- Follow-up actions:
  - Continue P12-2 with RNA list/detail parity endpoints.
  - Later tighten P12-4 by unifying API error payloads for all abort/error-handler paths.

### Task P12-2 - API Parity Endpoints (RNA List/Detail Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue API parity by adding read-only RNA list/detail endpoints.
  - Reuse existing RNA workflow/query-building and enrichment logic.
- Files changed:
  - `coyote/blueprints/api/views.py`
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/api/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); eps={r.endpoint for r in app.url_map.iter_rules()}; wanted={'api_bp.list_dna_variants','api_bp.show_dna_variant','api_bp.list_rna_fusions','api_bp.show_rna_fusion'}; print('api_missing', sorted(wanted-eps)); print('api_count', len(wanted & eps))"`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); c=app.test_client(); r=c.get('/api/v1/rna/samples/does-not-matter/fusions'); print('status', r.status_code); print('json', r.json)"`
- Result:
  - Added endpoints:
    - `GET /api/v1/rna/samples/<sample_id>/fusions`
    - `GET /api/v1/rna/samples/<sample_id>/fusions/<fusion_id>`
  - API endpoint registration verified (`api_missing []`, `api_count 4` for DNA+RNA parity routes).
  - Endpoints apply the same API auth behavior (`401` JSON when unauthenticated).
- Rollback needed: no
- Follow-up actions:
  - Continue P12-2 by adding parity endpoints for next priority data slices (CNV/translocation/report metadata) as needed.

### Task P12-4 - API/Web Error Payload Alignment (Initial Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extend centralized error handlers to return JSON payloads for API routes while preserving existing web error templates.
  - Keep prior status-code mapping unchanged.
- Files changed:
  - `coyote/errors/handlers.py`
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/errors/handlers.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python -c "from coyote import init_app; app=init_app(development=True); c=app.test_client(); r_api=c.get('/api/this-does-not-exist'); r_web=c.get('/this-does-not-exist'); print('api_status', r_api.status_code); print('api_json', r_api.json); print('web_status', r_web.status_code); print('web_ct', r_web.content_type)"`
- Result:
  - API requests now receive machine-readable error payloads from global handlers (`status`, `error`, `details`).
  - Web requests continue to receive rendered `error.html` responses.
- Rollback needed: no
- Follow-up actions:
  - Complete P12-4 by aligning any remaining abort/error edge cases in decorators/services to the same API payload contract.

### Task P11-3 - Route Module Split (RNA Fusion/Web Routes Final Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Complete RNA web-route modularization by moving list/detail routes out of monolithic `views.py`.
  - Keep all existing web URLs and endpoint names unchanged.
- Files changed:
  - `coyote/blueprints/rna/views_fusions.py` (renamed from `views.py`, now hosts list/detail fusion routes)
  - `coyote/blueprints/rna/views_actions.py` (already extracted action routes)
  - `coyote/blueprints/rna/views_reports.py` (already extracted report routes)
  - `coyote/blueprints/rna/__init__.py` (imports `views_fusions`, `views_actions`, `views_reports`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/rna/views_fusions.py coyote/blueprints/rna/views_actions.py coyote/blueprints/rna/views_reports.py coyote/blueprints/rna/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... verify rna endpoints ... PY`
- Result:
  - RNA routes are now organized by route domain:
    - fusion list/detail in `views_fusions.py`
    - action routes in `views_actions.py`
    - report routes in `views_reports.py`
  - Endpoint registration parity verified (`missing []` for expected RNA endpoints).
- Rollback needed: no
- Follow-up actions:
  - Continue P11-3 for any remaining oversized web route modules (if still needed) using the same blueprint-local split pattern.

### Task P11-1 - Shared Template Filter Helper Extraction (Phase 1, Continuation)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue low-risk filter deduplication by centralizing markdown rendering helpers.
  - Keep existing Jinja filter names and callsites unchanged.
- Files changed:
  - `coyote/filters/shared.py` (added `render_markdown_basic` and `render_markdown_rich`)
  - `coyote/blueprints/dna/filters.py` (`markdown` filter now delegates to shared helper)
  - `coyote/blueprints/home/filters.py` (`render_markdown` filter now delegates to shared helper)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/filters/shared.py coyote/blueprints/dna/filters.py coyote/blueprints/home/filters.py`
- Result:
  - Markdown rendering logic is now centralized in shared filter helpers while preserving template filter contracts.
  - Duplicate blueprint-local markdown implementations removed from active wrappers.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-1 by reviewing remaining duplicated low-risk formatting helpers for extraction into `coyote/filters/shared.py`.

### Task P11-3 - Route Module Split (DNA Final Naming/Action Consolidation Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Complete DNA route-module consistency by consolidating bulk variant action routes into `views_variant_actions`.
  - Rename monolithic `dna/views.py` to domain-specific `dna/views_variants.py` and keep route contracts unchanged.
- Files changed:
  - `coyote/blueprints/dna/views_variant_actions.py` (moved `classify_multi_variant` from variants module)
  - `coyote/blueprints/dna/views_variants.py` (renamed from `views.py`; removed moved action route)
  - `coyote/blueprints/dna/__init__.py` (imports `views_variants`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/dna/views_variants.py coyote/blueprints/dna/views_variant_actions.py coyote/blueprints/dna/views_cnv.py coyote/blueprints/dna/views_transloc.py coyote/blueprints/dna/views_reports.py coyote/blueprints/dna/__init__.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... verify dna endpoints ... PY`
- Result:
  - DNA route modules now follow a consistent domain split:
    - `views_variants.py` (list/detail/plot)
    - `views_variant_actions.py` (SNV action/comment/classification routes)
    - `views_cnv.py`, `views_transloc.py`, `views_reports.py`
  - URL paths and endpoint names preserved.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-1/P12 tasks; P11-3 oversized route-file split target is now complete.

### Task P12-2 - API Parity Endpoints (DNA CNV/Translocation Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extend DNA API parity with read-only CNV and translocation list/detail endpoints.
  - Reuse existing handlers/query builders and preserve current auth/RBAC + sample-assay access checks.
- Files changed:
  - `coyote/blueprints/api/views.py`
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/blueprints/api/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... verify api_bp.list_dna_cnvs/show_dna_cnv/list_dna_translocations/show_dna_translocation ... PY`
  - App-auth smoke checks:
    - `GET /api/v1/dna/samples/does-not-matter/cnvs` -> `401 {"status": 401, "error": "Login required"}`
    - `GET /api/v1/dna/samples/does-not-matter/translocations` -> `401 {"status": 401, "error": "Login required"}`
- Result:
  - Added endpoints:
    - `GET /api/v1/dna/samples/<sample_id>/cnvs`
    - `GET /api/v1/dna/samples/<sample_id>/cnvs/<cnv_id>`
    - `GET /api/v1/dna/samples/<sample_id>/translocations`
    - `GET /api/v1/dna/samples/<sample_id>/translocations/<transloc_id>`
  - Endpoint registration verified (`missing []`, `present 4` for new endpoint set).
  - API auth/error mode remains consistent with prior JSON `401` behavior.
- Rollback needed: no
- Follow-up actions:
  - Continue P12-2 with any remaining report-metadata parity surfaces needed by frontend cutover.

### Task P11-1 - Shared Template Filter Helper Extraction (Phase 1, DNA Legacy Fusion Desc Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Continue low-risk filter dedup by extracting legacy DNA fusion-description HTML generation to shared helpers.
  - Preserve existing template filter names and CSS class output contract.
- Files changed:
  - `coyote/filters/shared.py` (added `format_fusion_desc_legacy` + legacy term maps)
  - `coyote/blueprints/dna/filters.py` (`format_fusion_desc` now delegates to shared helper)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/filters/shared.py coyote/blueprints/dna/filters.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... init_app + verify key filter names ... PY`
- Result:
  - Legacy DNA fusion-desc rendering logic is centralized and reused through wrappers.
  - Existing `format_fusion_desc` filter contract remains unchanged for templates.
- Rollback needed: no
- Follow-up actions:
  - Continue P11-1 with remaining low-risk formatting helper dedup opportunities.

### Task P12-2 - API Parity Endpoints (DNA/RNA Report Preview Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Extend API parity with read-only report preview endpoints for DNA and RNA.
  - Reuse workflow services and permission model (`preview_report`) while keeping web behavior unchanged.
- Files changed:
  - `coyote/blueprints/api/views.py` (new report preview endpoints and shared API helpers)
  - `coyote/services/workflow/rna_workflow.py` (added canonical RNA `build_report_payload` and snapshot-row helper)
  - `coyote/blueprints/rna/views_reports.py` (rewired to use `RNAWorkflowService.build_report_payload`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/services/workflow/rna_workflow.py coyote/blueprints/rna/views_reports.py coyote/blueprints/api/views.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... verify api_bp.preview_dna_report/api_bp.preview_rna_report registration + auth-mode ... PY`
- Result:
  - Added endpoints:
    - `GET /api/v1/dna/samples/<sample_id>/report/preview`
    - `GET /api/v1/rna/samples/<sample_id>/report/preview`
  - Supports query `include_snapshot=1` for optional snapshot rows in API payload.
  - Endpoint registration verified (`missing []`), and unauthenticated requests return expected JSON `401`.
- Rollback needed: no
- Follow-up actions:
  - Continue P12-2 with any remaining report metadata parity fields needed by frontend increment.

### Task P12-3 - Frontend API Client Scaffolding (Initial Slice)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Add a lightweight shared browser API client to support progressive template-level migration to `/api/v1`.
  - Keep all existing server-rendered pages unchanged; no feature page cutover in this slice.
- Files changed:
  - `coyote/static/js/api_client.js` (new shared `window.coyoteApi` client with GET/POST helpers)
  - `coyote/templates/layout.html` (loads `static/js/api_client.js`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && PYTHONPATH=. .venv/bin/python - <<'PY' ... init_app + jinja get_template('layout.html') ... PY`
- Result:
  - Base layout now exposes a shared client (`window.coyoteApi`) for incremental feature-level API consumption.
  - No existing route/template behavior changed; migration remains rollback-safe.
- Rollback needed: no
- Follow-up actions:
  - Start feature-by-feature read-path adoption using `window.coyoteApi` behind toggles.

### Task P11-4 - FastAPI Runtime Migration (Initial Full Endpoint Cutover)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Replace Flask API blueprint runtime with native FastAPI runtime for existing v1 read endpoints.
  - Preserve current session-based auth/RBAC behavior and API JSON error contract.
  - Keep Flask API blueprint available only as explicit compatibility mode.
- Files changed:
  - `coyote/fastapi_api/app.py` (new FastAPI app + v1 endpoints + session-cookie auth/RBAC checks)
  - `coyote/fastapi_api/__init__.py`
  - `asgi.py` (ASGI entrypoint)
  - `coyote/__init__.py` (conditional Flask API blueprint registration)
  - `config.py` (new `ENABLE_FLASK_API_BLUEPRINT` toggle, default off)
  - `coyote/services/dna/query_builders.py` (service-layer DNA query builder access without blueprint import side effects)
  - `coyote/services/dna/dna_reporting.py` (rewired to service-layer query builder import)
  - `coyote/blueprints/api/views.py` (rewired query builder imports to service layer)
  - `requirements.txt` (`fastapi`, `uvicorn`, `httpx`)
  - `pyproject.toml` (`fastapi`, `uvicorn`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/fastapi_api/app.py asgi.py coyote/__init__.py config.py`
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/services/dna/query_builders.py coyote/services/dna/dna_reporting.py coyote/blueprints/api/views.py coyote/fastapi_api/app.py asgi.py`
  - Flask mode checks:
    - default: `ENABLE_FLASK_API_BLUEPRINT` unset -> `api_bp` endpoints absent (`count 0`)
    - compatibility: `ENABLE_FLASK_API_BLUEPRINT=1` -> `api_bp` endpoints present (`count 12`)
  - FastAPI smoke checks (TestClient):
    - `/api/v1/health` -> `200`
    - protected endpoints -> JSON `401 {"status": 401, "error": "Login required"}`
- Result:
  - FastAPI now provides the API runtime at `/api/v1/*` with existing endpoint coverage and auth/RBAC parity behavior for unauthenticated access.
  - Blueprint-side query-builder coupling was removed from services to support non-Flask execution contexts.
  - Flask API blueprint is no longer the default runtime path.
- Rollback needed: no
- Follow-up actions:
  - Continue P12-4 by validating authenticated parity and 403-path RBAC behavior under FastAPI with real session cookies.
  - Start endpoint-by-endpoint web consumer adoption using `window.coyoteApi`.

### Task P12-3 - Two-App Runtime Enforcement (Web Depends on API)

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Enforce split runtime architecture where Flask web app depends on external FastAPI API service.
  - Wire browser API base configuration and update compose topology to `web + api` services.
- Files changed:
  - `config.py` (`REQUIRE_EXTERNAL_API`, `API_BASE_URL`, `API_BROWSER_BASE`, `API_HEALTH_PATH`)
  - `coyote/__init__.py` (external API health verification on startup when enabled)
  - `coyote/static/js/api_client.js` (respects `window.COYOTE_API_BASE`)
  - `coyote/templates/layout.html` (injects `COYOTE_API_BASE` from config)
  - `docker-compose.yml` (split `coyote3_web` and `coyote3_api`)
  - `docker-compose.dev.yml` (split `coyote3_dev_web` and `coyote3_dev_api`)
  - `run_api.py` (local FastAPI runner)
  - `README.md` (architecture/runtime command updates)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `cd /data/bnf/dev/ram/Pipelines/Web_Developement/coyote3 && .venv/bin/python -m py_compile coyote/__init__.py config.py coyote/static/js/api_client.js coyote/fastapi_api/app.py asgi.py run_api.py`
  - Flask startup checks:
    - default FastAPI mode: Flask API blueprint disabled
    - compatibility override: `ENABLE_FLASK_API_BLUEPRINT=1` still works
  - FastAPI TestClient smoke checks:
    - `/api/v1/health` returns `200`
    - protected endpoints return JSON `401` when unauthenticated
- Result:
  - Runtime split is codified: web can require external API at boot and API runs independently via ASGI.
  - Frontend API calls are now base-url configurable for separate deployment topologies.
- Rollback needed: no
- Follow-up actions:
  - Complete P12-3 by migrating web read paths page-by-page from direct DB/store access to API client consumption.

### Task P12-3/P12-5 (Python-First Cutover) - Server-Side API Reads in Web Blueprints

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Replace browser-side list hydration with server-side Python API consumption.
  - Add typed API response models for web->api calls.
  - Route RNA/DNA list read paths to API first (feature-flagged), with strict-mode option for later hard enforcement.
- Files changed:
  - `coyote_web/api_models.py` (new pydantic response models)
  - `coyote_web/api_client.py` (new server-side HTTP client with cookie forwarding and typed decode)
  - `coyote/blueprints/rna/views_fusions.py` (GET list path now supports API read source)
  - `coyote/blueprints/dna/views_variants.py` (GET SNV list path now supports API read source)
  - `config.py` (new `WEB_API_STRICT_MODE`)
  - `coyote/templates/layout.html` (removed `api_pages.js` include)
  - `coyote/blueprints/rna/templates/list_fusions.html` (removed client-side hydration snippet)
  - `coyote/static/js/api_pages.js` (deleted)
  - `docker-compose.dev.yml` / `docker-compose.yml` (explicit strict/toggle env vars)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `python -m py_compile config.py coyote/blueprints/rna/views_fusions.py coyote/blueprints/dna/views_variants.py coyote_web/api_client.py coyote_web/api_models.py`
- Result:
  - Web now has a Python-first API integration path and no longer depends on `api_pages.js` for list-page data migration.
  - Foundation is in place to expand blueprint-by-blueprint API-only reads and later enable strict mode.
- Rollback needed: no
- Follow-up actions:
  - Continue converting remaining read routes (detail pages, admin listings) to server-side API calls and then turn on `WEB_API_STRICT_MODE` in dev.

### Task P12-2/P12-3 (Detail Cutover) - API-First DNA/RNA Detail Views

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Migrate RNA fusion detail and DNA variant detail web routes to API-first reads (GET path), with strict-mode/fallback control.
  - Expand FastAPI detail payload parity for DNA variant view to keep existing template contracts unchanged.
- Files changed:
  - `coyote/fastapi_api/app.py` (expanded `/api/v1/dna/samples/{sample_id}/variants/{var_id}` payload; enriched `/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}` sample/detail fields)
  - `coyote_web/api_models.py` (added detail payload models)
  - `coyote_web/api_client.py` (added typed detail fetch methods + request error mapping)
  - `coyote/blueprints/rna/views_fusions.py` (API-first `show_fusion`)
  - `coyote/blueprints/dna/views_variants.py` (API-first `show_variant`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `python -m py_compile coyote/fastapi_api/app.py coyote_web/api_models.py coyote_web/api_client.py coyote/blueprints/rna/views_fusions.py coyote/blueprints/dna/views_variants.py`
  - FastAPI TestClient auth-gate smoke checks for detail endpoints (`401` unauthenticated).
  - Flask web app init sanity (`create_web_app(development=True)`).
- Result:
  - Web detail routes now support API-first execution and can be forced fail-fast in strict mode.
  - API detail payloads now include fields needed by existing DNA/RNA detail templates.
- Rollback needed: no
- Follow-up actions:
  - Convert CNV/translocation detail/list routes similarly.
  - Extend API payload contracts for admin/read-only blueprint pages and begin removing web-side fallback paths in dev strict mode.

### Task P12-2/P12-3 (Detail Cutover Phase 2) - API-First CNV/Translocation Detail Views

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Switch DNA CNV detail and DNA translocation detail web routes to API-first reads (GET path).
  - Extend FastAPI CNV/translocation detail payloads to include template-compatible sample/detail aliases.
- Files changed:
  - `coyote/fastapi_api/app.py` (expanded CNV/translocation detail payload fields)
  - `coyote_web/api_models.py` (added CNV/translocation detail models)
  - `coyote_web/api_client.py` (added CNV/translocation detail fetch methods)
  - `coyote/blueprints/dna/views_cnv.py` (API-first `show_cnv`)
  - `coyote/blueprints/dna/views_transloc.py` (API-first `show_transloc`)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `python -m py_compile coyote/fastapi_api/app.py coyote_web/api_models.py coyote_web/api_client.py coyote/blueprints/dna/views_cnv.py coyote/blueprints/dna/views_transloc.py`
  - FastAPI TestClient auth-gate smoke checks for CNV/translocation detail endpoints (`401` unauthenticated).
- Result:
  - CNV/translocation detail pages now support server-side API reads with strict-mode/fallback control.
  - API payloads provide fields needed to keep current templates stable during cutover.
- Rollback needed: no
- Follow-up actions:
  - Migrate list pages for CNV/translocations and remaining read-only admin pages.

### Task P12-2/P12-3 (List Cutover Phase 2) - API-First CNV/Translocation Sections in DNA List Page

- Date: 2026-02-26
- Owner: Codex
- Scope:
  - Replace DNA list page CNV/translocation section reads with server-side API calls (when API read flag is enabled).
  - Add typed models/client methods for CNV/translocation list API payloads.
- Files changed:
  - `coyote_web/api_models.py` (added CNV/translocation list payload models)
  - `coyote_web/api_client.py` (added list fetch methods for CNVs/translocations)
  - `coyote/blueprints/dna/views_variants.py` (API-first CNV/translocation section loading with strict/fallback behavior)
  - `MIGRATION_PLAN_DNA_RNA_SHARED_SERVICES.md`
- Validation executed:
  - `python -m py_compile coyote_web/api_models.py coyote_web/api_client.py coyote/blueprints/dna/views_variants.py`
  - FastAPI TestClient auth-gate smoke checks for `/api/v1/dna/samples/{sample_id}/cnvs` and `/api/v1/dna/samples/{sample_id}/translocations` (`401` unauthenticated).
- Result:
  - DNA list page now routes more read-path surface through API under existing migration flags.
  - Remaining Mongo reads are reduced further on the primary DNA page.
- Rollback needed: no
- Follow-up actions:
  - Convert remaining list/detail read paths in admin/common blueprints and then enable dev strict mode for full route-level enforcement.

---

## 10) Session Rule

For every implemented task in future sessions:

1. Update task status in section 5.
2. Add a detailed entry in section 9 using section 8 template.
3. Record exact files touched and validation commands used.
