# Coyote3 Data Model Manual

## 1. Purpose and Scope
This document defines the database architecture for Coyote3 as an internal engineering reference. It is intended for backend engineers, platform maintainers, data migration authors, and reviewers responsible for validating change safety in a regulated clinical genomics environment. The focus is MongoDB data structures and usage patterns that enable clinical workflow correctness, policy enforcement, report traceability, and operational resilience under MongoDB 3.4 compatibility constraints.

All backend Mongo interaction is implemented under `api/infra/db/*`. The `api/db` package is not part of the architecture and must not be reintroduced.

This is not a high-level summary. The material below is written to support implementation decisions, code reviews, migration planning, and incident analysis. For each major structural decision, the document explains why the decision exists, what failure modes appear when the decision is violated, and what performance impact should be expected in production.

The model addresses:
- core collections and domain ownership
- relationship patterns among samples, variants, assays, users, and policy entities
- `SAMPLE_ID` as a cross-collection reference key
- versioned document structures with embedded changelog behavior
- environment-specific nested configuration patterns
- index strategy and query optimization
- MongoDB 3.4 constraints and their practical effects
- consistency expectations across multi-step write workflows
- migration and schema-evolution strategy
- schema-drift risk and control patterns
- canonical document examples

The data model should be read alongside architecture and API documentation, but this manual is intentionally self-contained so that database-level decisions can be reviewed without needing to infer details from route or UI code.

---

## 2. Data Modeling Principles for Coyote3
### 2.1 Principle: clinical workflows before generic abstraction
The data model exists to support real clinical workflows: sample review, interpretation, policy-controlled updates, and report generation with traceability. In practical terms, this means collection shapes are designed around actionable entities (sample, finding, report, role) rather than abstract normalization purity. A purely normalized model can reduce duplication but often increases query orchestration complexity and latency for common clinical operations. Coyote3 chooses a pragmatic balance: normalized enough to avoid uncontrolled duplication, denormalized enough to keep high-frequency workflows efficient and explicit.

**Why this exists**: users need predictable response times and traceable context while moving through complex review pipelines.

**What breaks if misused**: excessive normalization leads to many cross-collection lookups, increased code complexity, and higher probability of partial failures under non-transactional constraints.

**Performance implications**: query fan-out grows; route latency increases; caching pressure rises; index strategy becomes harder to align with endpoint behavior.

### 2.2 Principle: explicit domain ownership by collection family
Collections are grouped by domain responsibility: identity/policy, workflow findings, report lifecycle, and governance metadata. This clarity is critical for safe migrations and access-control review.

**Why this exists**: domain ownership reduces accidental coupling and simplifies audit/regulatory review.

**What breaks if misused**: mixed-purpose collections become difficult to version, difficult to protect with least privilege, and difficult to migrate without collateral behavior changes.

**Performance implications**: mixed collections often need broad indexes that degrade write throughput and query selectivity.

### 2.3 Principle: deterministic keys for cross-collection joins in application logic
MongoDB 3.4 does not provide modern transactional guarantees for multi-document workflows; therefore Coyote3 relies on deterministic key patterns and explicit service orchestration.

**Why this exists**: deterministic identifiers support repeat-safe operations and reconciliation.

**What breaks if misused**: if key fields are inconsistent by type or format (for example numeric vs string `SAMPLE_ID`), cross-collection retrieval fails silently or becomes brittle.

**Performance implications**: inconsistent keys force runtime coercion and prevent efficient index usage.

---

## 3. Core Collection Domains and Responsibilities
This section describes the major collection families and their role in workflow and policy operations.

## 3.1 Identity and Policy Collections
### 3.1.1 `users`
The `users` collection stores user identity attributes and policy overlays. It should contain stable identity fields (`username`, `email`, role linkage), operational status markers, and optional explicit permission adjustments.

Typical fields:
- `_id`
- `username`
- `email`
- `fullname`
- `role`
- `access_level` (optional resolved cache)
- `permissions` (explicit grants)
- `deny_permissions` (explicit denials)
- `is_active`
- metadata fields (`created_on`, `updated_on`, `updated_by`)

**Why this structure exists**: user documents need both role mapping and exception capability without requiring schema mutation for each exceptional account.

**What breaks if misused**: storing policy logic only in free-form fields or text notes prevents deterministic policy evaluation and creates authorization drift.

**Performance implications**: frequent auth lookups require indexed `username` and often `email`; missing indexes can cause login latency spikes.

### 3.1.2 `roles`
Roles represent policy bundles and level semantics.

Typical fields:
- `_id` (role id)
- `label`
- `level`
- `permissions`
- `deny_permissions`
- `is_active`
- version/changelog metadata

**Why this structure exists**: role-level defaults reduce repetitive permission assignment and support governance review.

**What breaks if misused**: if roles are edited without changelog/version controls, authorization changes become hard to explain post-incident.

**Performance implications**: role reads are frequent but small; indexed `_id` lookups are sufficient in most deployments.

### 3.1.3 `permissions`
Permission registry defines operation-level capabilities and category taxonomy.

Typical fields:
- `_id` (permission id)
- `label`
- `category`
- `description`
- `is_active`

**Why this structure exists**: policy needs explicit and reviewable action identifiers.

**What breaks if misused**: permission names drifting from route enforcement points leads to governance mismatch (documented permission with no runtime effect or runtime checks referencing undefined permission).

**Performance implications**: low write volume; read-heavy in admin workflows; basic indexing by `_id` and `category` typically sufficient.

### 3.1.4 `schemas`
Dynamic configuration schema definitions used by admin and workflow configuration surfaces.

Typical fields:
- `_id`
- `schema_type`
- `schema_category`
- `version`
- `fields`
- `is_active`
- changelog/version metadata

**Why this structure exists**: controlled runtime flexibility for evolving assay and governance rules.

**What breaks if misused**: malformed schema definitions can break entire admin flows or produce invalid payload acceptance/rejection.

**Performance implications**: relatively small collection; reads mostly by id/type; validation complexity is CPU-side in API, not DB-side.

## 3.2 Clinical Workflow Collections
### 3.2.1 `samples`
`sample` is the central entity linking case context, assay identity, filter state, and report references.

Typical fields:
- `_id`
- `SAMPLE_ID` or equivalent canonical identifier
- `name`
- `case_id`
- `assay`
- `profile` / environment metadata
- `filters`
- `reports` (embedded references or summary list)
- optional sample comments/history

**Why this structure exists**: sample-centric workflows need fast retrieval of contextual metadata.

**What breaks if misused**: if assay fields are inconsistent or optional without defaults, UI and service routing can invoke wrong workflow logic.

**Performance implications**: one of the highest read collections; indexing on sample and case identifiers is mandatory.

### 3.2.2 `variants`
Stores DNA variant-level records associated to a sample.

Typical fields:
- `_id`
- `SAMPLE_ID`
- genomic coordinates (`CHROM`, `POS`, `REF`, `ALT`)
- derived identifiers (`simple_id`, hash)
- annotation blocks
- classification/tier markers
- flags/comments linkage references

**Why this structure exists**: variant workflows require coordinate and annotation fields with assay-aware filtering.

**What breaks if misused**: inconsistent coordinate typing or missing derived identifiers can break search and context endpoints.

**Performance implications**: potentially large cardinality; indexing strategy must align with `SAMPLE_ID` and common filter keys.

### 3.2.3 `cnvs` and `translocs`
Collections for non-SNV DNA findings, linked to sample context.

**Why this structure exists**: domain separation preserves query clarity and avoids sparse wide documents mixing fundamentally different evidence types.

**What breaks if misused**: collapsing all finding types into one wide collection creates sparse-index complexity and fragile route logic.

**Performance implications**: separate collections improve selectivity and reduce payload overhead for modality-specific pages.

### 3.2.4 `fusions`
RNA fusion findings linked to sample context and call details.

**Why this structure exists**: RNA workflows have distinct filtering and call selection semantics.

**What breaks if misused**: sharing DNA structures for fusion logic leads to field overloading and interpretation confusion.

**Performance implications**: supports RNA-specific index and query patterns without affecting DNA query plans.

## 3.3 Reporting and Traceability Collections
### 3.3.1 `reports`
Report metadata for saved report artifacts.

Typical fields:
- `_id`
- `sample_oid` or `SAMPLE_ID`
- `report_id`
- `report_num`
- `filepath`
- `created_by`
- `created_on`

**Why this structure exists**: report lifecycle must be reconstructable independently of file storage.

**What breaks if misused**: if file path exists without metadata linkage, report history becomes incomplete.

**Performance implications**: index by `report_id` and sample reference is critical for history lookups.

### 3.3.2 `reported_variants`
Snapshot records of finding context at report-save time.

Typical fields:
- `_id`
- `sample_oid` / sample identifiers
- `report_oid`, `report_id`
- finding reference fields
- tier/classification snapshot
- created metadata

**Why this structure exists**: preserves report-time evidence state even if base findings evolve later.

**What breaks if misused**: relying only on live variant state for report reconstruction can produce irreproducible historical reports.

**Performance implications**: can grow quickly; indexing by `report_oid`, `report_id`, and sample linkage needed.

## 3.4 Governance and Audit Collections
### 3.4.1 audit events collection (name may vary)
Stores structured event envelopes for significant operations.

**Why this structure exists**: supports accountability and incident reconstruction.

**What breaks if misused**: partial or inconsistent event payloads make forensic analysis unreliable.

**Performance implications**: append-heavy; index by timestamp, actor, entity reference for efficient retrieval.

---

## 4. Relationships Between Samples, Variants, Assays, and Users
### Conceptual relationship model
- User acts on sample workflows according to role/permission.
- Sample references assay context.
- Findings collections (`variants`, `cnvs`, `fusions`, etc.) reference sample through `SAMPLE_ID` pattern.
- Reports reference sample and capture snapshot rows linked to specific report ids.

Textual relationship diagram:

```text
users -> roles -> permissions
users -> actions on samples/findings/reports (audited)
samples -> variants/cnvs/translocs/fusions (by SAMPLE_ID)
samples -> reports (history linkage)
reports -> reported_variants snapshots
```

### Why this relationship style exists
Coyote3 optimizes for sample-centered read workflows while preserving actor attribution and policy context. Relationship pathways are explicit and mostly one-way from contextual anchors (sample/report) to dependent entities.

### What breaks if misused
If findings are linked to sample inconsistently (different key formats), route-family queries become unreliable. If report snapshots are not linked clearly to report ids, historical reconstructions fail.

### Performance implications
Consistent relationship keys enable targeted compound indexes and reduce expensive cross-collection correlation logic.

---

## 5. SAMPLE_ID Reference Pattern
`SAMPLE_ID` (or an equivalent normalized sample key) is the primary cross-collection reference strategy for findings and many workflow operations.

### Pattern definition
- `SAMPLE_ID` must be represented consistently as string.
- It must be present in findings documents that belong to a sample-centric workflow.
- It should align with sample `_id` or a deterministic mapping convention documented in handlers.

### Why this exists
A deterministic reference field simplifies high-frequency queries and avoids expensive joins at application level.

### What breaks if misused
- inconsistent type (`int` in one collection, `str` in another)
- inconsistent casing/formatting
- absent `SAMPLE_ID` in subset of documents

These issues cause subtle missing results and broken context pages.

### Performance implications
Uniform `SAMPLE_ID` fields support simple selective indexes and fast filter predicates.

### Implementation guideline
Enforce `SAMPLE_ID` normalization in ingestion and migration layers rather than patching at query-time repeatedly.

### Example query

```python
variants = store.variant_handler.collection.find({'SAMPLE_ID': sample_id})
fusions = store.fusion_handler.collection.find({'SAMPLE_ID': sample_id})
```

---

## 6. Versioned Document Structure with Embedded Changelog
Certain collections (roles, schemas, assay configs, governance docs) should be version-aware and store change metadata.

### Recommended structure pattern

```json
{
  "_id": "aspc_wgs_v3",
  "version": 3,
  "is_active": true,
  "payload": {...},
  "changelog": [
    {
      "revision": 1,
      "action": "create",
      "actor": "admin_a",
      "timestamp": "2026-02-20T10:00:00Z",
      "reason": "Initial definition"
    },
    {
      "revision": 2,
      "action": "update",
      "actor": "admin_b",
      "timestamp": "2026-02-27T09:00:00Z",
      "reason": "Adjusted default filter"
    }
  ],
  "updated_on": "2026-02-27T09:00:00Z",
  "updated_by": "admin_b"
}
```

### Why this exists
Regulated operations require historical reconstruction and controlled rollback without destructive history loss.

### What breaks if misused
If changelog entries are optional or inconsistently populated, rewind decisions become weak and audit value drops. If version numbers are overwritten or non-monotonic, trust in revision chronology is reduced.

### Performance implications
Embedded changelog arrays can grow; for high-churn entities, consider bounded embedded changelog with archival strategy if document size becomes concern under Mongo limits.

---

## 7. Environment-Specific Nested Configuration
Coyote3 uses nested configuration for environment-dependent behavior where necessary (for example dev/prod profile variants).

### Pattern example

```json
{
  "_id": "rna_filter_schema_v2",
  "schema_type": "rna_filter",
  "profiles": {
    "dev": {"defaults": {"min_spanning_reads": 1}},
    "prod": {"defaults": {"min_spanning_reads": 3}}
  }
}
```

### Why this exists
Operational environments may require different defaults or toggles while sharing core schema identity.

### What breaks if misused
- missing profile fallback behavior
- silent fallback to unrelated profile
- mixing environment and role concerns in one nested object

These patterns create ambiguous runtime behavior.

### Performance implications
Nested configuration retrieval is cheap; performance risk is mainly logical complexity and cache invalidation, not query cost.

### Implementation guideline
Define explicit fallback order in service layer and test each profile behavior.

---

## 8. Index Strategy and Rationale
Indexes should reflect actual workload, not theoretical completeness.

## 8.1 High-priority index families
1. Identity lookups: `users.username`, `users.email`.
2. Policy lookups: `roles._id`, `permissions._id`.
3. Workflow lookups: `samples._id`, `samples.case_id`, findings by `SAMPLE_ID`.
4. Reporting lookups: `reports.report_id`, `reports.sample_oid`, snapshots by `report_oid`.
5. Audit lookup patterns: timestamp + actor/entity filters.

## 8.2 Why this strategy exists
Route-family behavior is dominated by sample/finding retrieval and policy checks. Index policy must align with these reads first.

## 8.3 What breaks if misused
- Over-indexing increases write overhead and memory pressure.
- Under-indexing creates slow queries and UI instability.
- Wrong compound index order results in low selectivity.

## 8.4 Performance implications
- Well-chosen indexes reduce p95 latency for list/search endpoints.
- Poor index plans can amplify operational load quickly as dataset grows.

### Example index commands

```javascript
db.users.createIndex({"username": 1}, {unique: true})
db.samples.createIndex({"case_id": 1})
db.variants.createIndex({"SAMPLE_ID": 1, "POS": 1})
db.reports.createIndex({"report_id": 1}, {unique: true})
db.reported_variants.createIndex({"report_oid": 1})
```

---

## 9. Query Optimization Patterns
Optimization in Coyote3 means predictable latency for clinically relevant workflows, not only raw benchmark throughput.

## 9.1 Pattern: projection discipline
Query only fields needed for endpoint response.

**Why**: reduces network and serialization overhead.

**What breaks if misused**: broad projections can inflate memory and response latency.

### Example

```python
store.sample_handler.collection.find_one({'_id': sample_id}, {'_id': 1, 'assay': 1, 'case_id': 1})
```

## 9.2 Pattern: paginated retrieval
List endpoints should page results.

**Why**: bounded payloads reduce latency spikes and memory pressure.

**What breaks if misused**: unbounded list endpoints degrade user experience and can cause timeout behavior.

## 9.3 Pattern: avoid N+1 collection loops
Aggregate needed identifiers, then perform batched queries.

**Why**: reduces repeated round trips.

**What breaks if misused**: route latency grows linearly with row count and can become unstable.

## 9.4 Pattern: stable sort fields with index support
Sorting on non-indexed fields in large collections is expensive.

**Why**: sorted output often required in UI lists.

**What breaks if misused**: blocking sorts and high latency under load.

---

## 10. Backward Compatibility Constraints (MongoDB 3.4)
MongoDB 3.4 imposes constraints that influence architecture and coding patterns.

### Key constraints
- no modern multi-document transaction semantics
- limited feature set vs newer Mongo versions
- migration scripts and query operators must remain compatible

### Why compatibility exists
Institutional infrastructure and migration risk profiles require continued support for 3.4-compatible behavior.

### What breaks if misused
Using unsupported operators or transaction assumptions can pass local modern Mongo tests but fail in target environments.

### Performance implications
Some modern optimization strategies are unavailable; application-layer orchestration must be efficient and conservative.

### Implementation guidance
- validate scripts in environment-compatible context
- keep query syntax conservative
- document any optional modern-path logic clearly if introduced for future migration

---

## 11. Data Consistency Expectations
Because transactional guarantees are limited, consistency is enforced by application orchestration and careful write sequencing.

### Consistency model
- use ordered writes for multi-entity operations
- enforce precondition checks before mutation
- fail fast on critical write errors
- provide reconciliation strategy for partial failures

### Why this exists
Clinical workflows cannot tolerate silent partial success where report metadata exists but snapshot rows do not, or vice versa.

### What breaks if misused
Inconsistent write ordering and missing checks create orphaned or mismatched records.

### Performance implications
Additional validation and sequencing adds overhead, but this is necessary to preserve correctness.

### Example report save ordering
1. validate output path
2. write report artifact
3. persist report metadata
4. persist reported variant snapshot rows
5. emit audit event

---

## 12. Migration Strategy
Migrations should be controlled, testable, and reversible where possible.

## 12.1 Recommended phased approach
1. Additive schema introduction (non-breaking).
2. Dual-shape code support.
3. Backfill migration script with dry-run mode.
4. Validation run (read checks + endpoint checks).
5. Legacy-path removal after approved window.

## 12.2 Why this exists
Clinical continuity requires minimizing disruption. Incremental migration lowers risk.

## 12.3 What breaks if misused
One-step destructive migrations can break live endpoints and make rollback difficult.

## 12.4 Performance implications
Batching is needed to avoid large migration spikes that impact operational workloads.

### Example dry-run script pattern

```python
DRY_RUN = True
BATCH = 1000
query = {'new_field': {'$exists': False}}
# count candidates and report before writes
```

---

## 13. Risks of Schema Drift
Schema drift means document shapes diverge from expected contracts over time.

### Drift sources
- ad hoc manual updates
- incomplete migrations
- inconsistent ingestion paths
- optional fields without clear defaults

### Why this matters
Drift causes hidden failures in route/service logic and can produce inconsistent UI behavior.

### What breaks if misused
- contract tests fail unpredictably
- missing field exceptions
- incorrect policy interpretations

### Performance implications
Drift forces runtime normalization logic, increasing CPU and complexity.

### Drift controls
- schema validation at API entry
- migration validation checks
- periodic collection shape audits
- fixture snapshots aligned with latest document patterns

---

## 14. Example Documents for Major Collections
## 14.1 User

```json
{
  "_id": "u1",
  "username": "analyst1",
  "email": "analyst1@example.org",
  "fullname": "Analyst One",
  "role": "analyst",
  "permissions": ["view_sample", "view_variant"],
  "deny_permissions": [],
  "is_active": true,
  "updated_on": "2026-03-03T10:00:00Z",
  "updated_by": "admin_user"
}
```

## 14.2 Role

```json
{
  "_id": "analyst",
  "label": "Analyst",
  "level": 100,
  "permissions": ["view_sample", "view_variant", "preview_report"],
  "deny_permissions": ["delete_sample_global"],
  "is_active": true,
  "version": 4,
  "changelog": [
    {"revision": 1, "action": "create", "actor": "admin", "timestamp": "2025-11-01T08:00:00Z", "reason": "Initial role"}
  ]
}
```

## 14.3 Permission

```json
{
  "_id": "preview_report",
  "label": "Preview report",
  "category": "REPORTING",
  "description": "Allows report preview endpoints",
  "is_active": true
}
```

## 14.4 Sample

```json
{
  "_id": "s1",
  "SAMPLE_ID": "SAMPLE_001",
  "name": "SAMPLE_001",
  "case_id": "CASE001",
  "assay": "WGS",
  "profile": "production",
  "filters": {
    "min_depth": 100,
    "min_alt_reads": 5
  },
  "reports": [
    {"report_id": "CASE001_CC1.260303101112", "report_num": 1}
  ]
}
```

## 14.5 Variant

```json
{
  "_id": "v1",
  "SAMPLE_ID": "SAMPLE_001",
  "CHROM": "17",
  "POS": 7579472,
  "REF": "C",
  "ALT": "T",
  "simple_id": "17_7579472_C_T",
  "tier": 2,
  "annotation": {
    "gene": "TP53",
    "consequence": "missense_variant"
  }
}
```

## 14.6 Fusion

```json
{
  "_id": "f1",
  "SAMPLE_ID": "SAMPLE_001",
  "gene1": "EML4",
  "gene2": "ALK",
  "calls": [{"selected": 1, "breakpoint1": "2:42522694", "breakpoint2": "2:29443657"}],
  "classification": {"class": 2}
}
```

## 14.7 Report

```json
{
  "_id": "r1",
  "sample_oid": "s1",
  "sample_name": "SAMPLE_001",
  "report_id": "CASE001_CC1.260303101112",
  "report_num": 1,
  "filepath": "/reports/dna/CASE001_CC1.260303101112.html",
  "created_by": "analyst1",
  "created_on": "2026-03-03T10:11:12Z"
}
```

## 14.8 Reported Variant Snapshot

```json
{
  "_id": "rv1",
  "sample_oid": "s1",
  "report_oid": "r1",
  "report_id": "CASE001_CC1.260303101112",
  "simple_id": "17_7579472_C_T",
  "gene": "TP53",
  "tier": 2,
  "created_by": "analyst1",
  "created_on": "2026-03-03T10:11:12Z"
}
```

## 14.9 Schema Document

```json
{
  "_id": "aspc_schema_v1",
  "schema_type": "assay_config",
  "schema_category": "ASSAY",
  "version": 1,
  "fields": {
    "analysis_types": {"type": "list", "default": []},
    "reporting": {"type": "object", "default": {}}
  },
  "is_active": true,
  "changelog": [
    {"revision": 1, "action": "create", "actor": "admin", "timestamp": "2026-02-20T10:00:00Z", "reason": "Initial schema"}
  ]
}
```

## 14.10 Audit Event

```json
{
  "_id": "ae1",
  "event_type": "report.save",
  "entity_type": "report",
  "entity_id": "r1",
  "actor_id": "u1",
  "result": "success",
  "timestamp": "2026-03-03T10:11:13Z",
  "metadata": {"sample_id": "SAMPLE_001", "report_id": "CASE001_CC1.260303101112"}
}
```

---

## 15. Safely Evolving Document Structures
Document evolution must be planned as operational change, not only code change.

### 15.1 Evolution rules
1. Define target shape and compatibility window.
2. Add schema and service support for both old and new shape.
3. Introduce migration script with dry-run.
4. Execute batch migration with monitoring.
5. Validate by route-level behavior tests.
6. Remove legacy support after approved window.

### 15.2 Why this exists
Safe evolution protects live workflows and minimizes report-generation disruptions.

### 15.3 What breaks if misused
Direct hard cutovers can break old documents in live paths and produce incident cascades.

### 15.4 Performance implications
Dual-shape handling introduces temporary CPU overhead; keep compatibility windows bounded and remove legacy branches promptly.

### Example dual-shape access pattern

```python
def get_min_spanning_reads(filters: dict) -> int:
    if 'min_spanning_reads' in filters:
        return int(filters['min_spanning_reads'])
    if 'spanning_reads' in filters:  # legacy
        return int(filters['spanning_reads'])
    return 0
```

---

## 16. Structural Decision Checklist for Reviewers
When reviewing data model changes, validate:
1. Domain ownership clarity of affected collection.
2. Key reference consistency (`SAMPLE_ID` and related ids).
3. Backward compatibility plan.
4. Index impact analysis.
5. Migration and rollback strategy.
6. Audit/changelog metadata handling.

This checklist is mandatory for high-impact changes (policy, reporting, schema, assay behavior).

---

## 17. Assumptions
ASSUMPTION:
- Collection names may vary slightly by deployment profile, but domain roles described here remain valid.
- API core modules remain the authoritative layer for policy and workflow orchestration.
- MongoDB 3.4 compatibility remains an active constraint.

---

## 18. Future Evolution Considerations
1. Introduce formal schema registry validations at ingestion and mutation boundaries.
2. Add automated collection-shape drift reports in CI or scheduled operations.
3. Upgrade Mongo platform with staged compatibility test matrix.
4. Add signed audit event archival and cross-system evidence packaging.
5. Expand query performance observability for route-family hotspots.

---

## 19. Data Model Governance, Ownership Workflow, and Operational Anti-Patterns
Strong data models degrade quickly when ownership is ambiguous. In Coyote3, every structural change to a governed collection should have an identified owner, an expected impact scope, and a testable migration path. Ownership does not mean a single engineer writes all changes. It means there is a responsible domain maintainer who can answer three questions clearly: what changed, why it changed, and how rollback works. This discipline prevents silent schema divergence and reduces incident duration when behavior changes unexpectedly.

A safe governance workflow includes proposal, review, implementation, validation, and post-deploy verification stages. Proposal should specify targeted collection(s), field-level changes, compatibility requirements, and index implications. Review should include API/service maintainers who consume those fields and operations staff who understand runtime impact. Implementation should keep changes isolated and reversible where possible. Validation should include both direct data checks and route-family tests, because structurally valid documents can still fail business contracts. Post-deploy verification should confirm that query latencies and error rates remain within normal bounds.

The most common operational anti-pattern is “just one manual update in database.” Manual edits bypass validation and can introduce field drift that is hard to detect until a workflow breaks. Another anti-pattern is changing field meaning without changing field name. For example, if a field originally represented absolute threshold and is later treated as percentage without renaming or migration metadata, downstream behavior can become silently incorrect. A third anti-pattern is adding optional fields with no defaults and then treating them as required in service code. This creates delayed failure modes as soon as older documents are encountered.

A performance-related anti-pattern is adding broad indexes reactively for one slow query without reviewing write cost and cardinality. In high-write collections such as finding snapshots or audit events, unnecessary indexes can significantly increase write latency and storage overhead. Index changes should always be justified with query evidence and reviewed in context of write volume.

These governance controls exist because schema correctness in Coyote3 is not only an engineering concern; it is a clinical safety concern. A drifted field or inconsistent reference can change what users see, what they can act on, and what report artifacts represent. Treating data model governance as a first-class engineering workflow is therefore part of maintaining trustworthy clinical software.
