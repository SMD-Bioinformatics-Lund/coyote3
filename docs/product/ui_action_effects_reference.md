# User Action and Operational Impact Reference

This reference document maps platform user interface controls to their corresponding backend execution endpoints, persistent state mutations, and primary visual outcomes. It serves as the definitive functional contract for Quality Assurance and System Engineering.

## Core Sample Orchestration

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply selected** | Gene List Selection | `POST /home/<id>/apply_isgl` | `samples.filters.genelists` | Update of effective gene scope and variant summaries. |
| **Save (Ad-Hoc)** | Ad-Hoc Gene Entry | `POST /home/<id>/adhoc_genes` | `samples.filters.adhoc_genes` | Insertion of targeted gene inclusions. |
| **Clear Ad-Hoc** | Sample Settings | `POST /home/<id>/adhoc_genes/clear` | `samples.filters.adhoc_genes` (NULL) | Reversion of gene scope to baseline config. |
| **Download** | Report Catalog | Service file stream | (Read-only) | Local archival retrieval of report PDF/JSON. |

## DNA Interpretation Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply (Filters)** | Discovery Sidebar | `PUT /samples/{id}/filters` | `samples.filters` (DNA) | Recalculation of findings within active review tables. |
| **Reset** | Discovery Sidebar | `DELETE /samples/{id}/filters` | `samples.filters` (Defaults) | Re-initialization of assay-original thresholds. |
| **Apply (Bulk)** | Bulk Action Panel | Patch bulk orchestration | Multi-document Tier/Flag updates | Synchronization of clinical state across selected cohorts. |
| **Finalize Report** | Report Preview | Report creation endpoint | `reported_variants` snapshots | Generation of immutable clinical report record. |

## Finding-Level Clinical Interactions (SNV, CNV, SV)

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Mark False Positive** | Detail Views | `PATCH .../flags/false-positive` | `fp` flag status | finding removal from prioritized review streams. |
| **Classify (Tier)** | Classification Panel | `POST .../classifications` | `annotations.class` | Formal clinical tier assignment applied. |
| **Remove Class** | Classification Panel | `DELETE .../classifications` | Mutation of active annotation index | Clearance of clinical priority markers. |
| **Save Comment** | Annotation Form | `POST .../annotations` | `annotations` collection record | Persistence of review notes and diagnostic audit trail. |
| **Add to Blacklist** | Variant Details | `POST .../blacklist_entries` | `blacklist` collection update | Systematic exclusion from future center-level findings. |

## RNA Interpretation Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply (Filters)** | Fusion Sidebar | `PUT /samples/{id}/filters` | `samples.filters` (RNA) | Dynamic recalculation of fusion visibility. |
| **Pick Call** | Fusion Detail | `PATCH .../selection/{idx}` | `fusions.selected_call` mutation | Designation of primary diagnostic evidence source. |
| **Classify Fusion** | Fusion Detail | Classification endpoint | `annotations` tier context | Tier assignment for targeted fusion event. |

## Administrative and Governance Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Save User** | Identity Management | `POST/PUT /admin/users` | `users` collection record | Mutated organizational user identity. |
| **Toggle Status** | Administrator Lists | `PATCH .../status` | `is_active` boolean | Modification of resource accessibility. |
| **Send Invite** | User Management | `POST .../invite` | Crypto-token generation | Email-link delivery or manual credential hand-off. |
| **Save Policy** | Roles/Permissions | Authorization endpoints | `roles` / `permissions` docs | Real-time update of RBAC enforcement policies. |
| **Save Panel/Config** | Assay Resources | ASP/ASPC endpoints | `asp_configs` / `assay_specific_panels` | Versioned update of center-level analytic logic. |

## Local Interface Controls (Non-Persistent)

The following controls manipulate the Browser Document Object Model (DOM) without triggering persistent backend state changes:
- **Hide False Positives**: Localized visibility toggle for finding filters.
- **Navigation Collapse**: Sidebar and menu layout orchestration.
- **Pagination**: Local table paging within client-orchestrated datasets.
- **Expand/Collapse**: User-driven text visibility for long descriptions.
- **Chart Toggles**: Analytical chart mode switching (e.g., Target vs. Evidence).

## Quality Assurance Execution Protocol

Analytical verification of UI actions must confirm:
1. **Interactive Trigger**: Successful UI invocation of the targeted control.
2. **Transactional Acknowledgement**: Verification of successful API response headers.
3. **Persistence Verification**: Refresh-based confirmation of server-side state commitment.
4. **Contextual Propagation**: Validation that related summaries (e.g., report totals) acknowledge the mutation.
