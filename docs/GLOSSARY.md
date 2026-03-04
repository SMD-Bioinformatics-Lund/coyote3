# Coyote3 Glossary

## 1. Clinical and Genomics Terms
- **Assay**: A laboratory method used to detect, quantify, or characterize genomic alterations from a sample.
- **Assay Group**: A logical grouping of assays sharing workflow rules, interpretation behavior, and reporting profile.
- **Variant**: A genomic difference from reference sequence.
- **SNV**: Single nucleotide variant.
- **CNV**: Copy number variant.
- **Fusion**: A rearrangement event joining genomic segments, often represented in RNA-focused workflows.
- **Translocation**: Structural rearrangement involving segment movement between chromosomes.
- **Tiering**: Clinical prioritization classification used to stratify evidence and reporting relevance.
- **Sample**: A case-linked biological specimen with metadata, assay context, and analysis outputs.
- **Panel**: A predefined gene or target set used for analysis and filtering behavior.

## 2. Coyote3 Domain Terms
- **Sample Context**: Aggregated backend payload for a sample-specific page/workflow.
- **Assay Config**: Runtime configuration object controlling filtering, interpretation, and report behavior.
- **Schema-driven Configuration**: Configuration whose accepted fields and sections are controlled by a schema document.
- **Version History**: Embedded history sequence recording configuration versions and changes.
- **Snapshot Rows**: Structured rows captured during report save path for reproducible report context.
- **Preview Report**: Non-persisted report payload/template context generated for rendering validation.
- **Persisted Report**: Saved report artifact and metadata written through report save flow.

## 3. Security and Access Terms
- **RBAC**: Role-based access control.
- **Permission**: Named access capability assigned through role policy.
- **Deny Permission**: Explicit permission denial that overrides corresponding allow assignment.
- **Access Level**: Numeric authorization tier used by `require_access(...)` in combination with permission/role checks.
- **Policy Category**: Grouping dimension for related permission definitions.

## 4. Architecture and Implementation Terms
- **Route Layer**: FastAPI endpoint definitions in `api/routes/*`.
- **Core Layer**: Domain orchestration logic in `api/core/*`, implemented as framework-agnostic modules.
- **Handler Layer**: MongoDB query/write interfaces in `api/infra/db/*`.
- **Blueprint**: Flask module grouping routes and templates for a UI domain.
- **API Client Facade**: Flask-side HTTP client abstraction in `coyote/services/api_client/api_client.py`.
- **Web Report Bridge**: UI service layer module handling report preview/save API orchestration.

## 5. Testing and Operations Terms
- **Contract Test**: Validation of request/response behavior at route boundary.
- **Integration Test**: Multi-layer test spanning route, service, and persistence abstraction behavior.
- **Mutation Testing**: Test robustness method that intentionally mutates code to detect weak assertions.
- **Rollback**: Controlled deployment reversal preserving data and service integrity.
- **Compatibility Window**: Time-limited period where old and new contracts/document shapes are supported simultaneously.
