# Management Guide

The Management suite is designed for platform administrators, laboratory leads, and data managers to govern the Coyote3 environment. It covers identity management, clinical resource configuration, and system-wide audit oversight for users granted `audit_log:view`.

![Coyote3 administration workspace](../assets/screenshots/admin.png)

## 1. User and Role Administration

Manage the identities of clinical and technical staff authorized to access the platform.

### User Management
*   **Creating Users**: Add staff by providing their official credentials and clinical profession.
*   **Professional Profiles**: Assign roles such as "Clinician," "Bioinformatician," or "Quality Manager" to ensure audit trails reflect the correct clinical responsibility.
*   **Account Status**: Enable or disable access instantly to maintain laboratory security.
*   **Authentication Providers**: User accounts show one badge for each enabled provider. `LDAP` indicates center directory authentication by email. `Local` indicates Coyote3-managed password authentication by username. Accounts can carry both providers when a center needs a transition or fallback path.
*   **Email Links**: Email addresses in user tables and read-only user views open the configured mail client through a `mailto:` link.

### Role-Based Access Control (RBAC)
Coyote3 uses a granular role system where specific permissions are grouped into manageable roles.

*   **Standard Roles**: "Admin," "User," and "Guest" provide predefined access buckets.
*   **Custom Roles**: Administrators can define library-specific roles (e.g., "Lead Clinical Reviewer") to match the laboratory's operational hierarchy.
*   **Role Badges**: Roles are rendered as compact color chips. The configured role color is shown as a dot and subtle border/background accent while the text remains high-contrast for readability in light and dark mode.
*   **Highest Role Display**: Summary surfaces show the highest effective role. Profile and user-management screens show all assigned roles so account scope can be audited directly.

Default role palette:

| Role | Accent color | Purpose |
| --- | --- | --- |
| `admin` | Red | Administrative control and high-impact system configuration. |
| `developer` | Blue | Engineering and integration-level access. |
| `tester` | Amber | Validation and test workflow access. |
| `manager` | Indigo | Operational oversight and review coordination. |
| `user` | Green | Standard clinical or laboratory user access. |
| `intern` | Purple | Restricted training or supervised access. |
| `viewer` | Slate | Read-only access. |
| `external` | Slate gray | External or limited collaborator access. |

Role colors should be stored as hex values in the role document. The UI may normalize simple named colors, but center-managed palettes should use explicit hex colors for consistent rendering.

---

## 2. Resource Configuration (ASP / ASPC)

The platform's analytical logic is driven by Assay Service Profiles (ASP), Assay Service Performance Configurations (ASPC), and In-Silico Gene Lists (ISGL).

### Assay Service Profiles (ASP)
An ASP is the "Scientific Definition" of an assay. It defines:
*   The targeted gene panel (ISGL).
*   The genomic build (GRCh37/38).
*   Quality thresholds and analytical pipelines.
*   The configured assay category, assay group, assay family, sequencing platform, and read mode.

Values backed by platform constants, such as `DNA`, `RNA`, `hematology`, `solid`, `panel-dna`, `wgs`, `illumina`, and `nanopore`, are shown as semantic badges in admin tables and read-only views. This makes configuration scans faster without relying on raw text alone.

### Assay Service Performance Configurations (ASPC)
ASPCs are the "Software Profiles" that determine how a physical assay is handled in the UI.
*   **Interpretation Pipelines**: Configure which filters (Allelic Fraction, Depth, Population Frequency) are applied by default during clinical review.
*   **Reporting Templates**: Link specific assays to their finalized PDF report designs.
*   **Analysis Types**: Enabled domains such as `SNV`, `CNV`, `TRANSLOCATION`, `BIOMARKER`, `FUSION`, `EXPRESSION`, and `QC` are rendered as color-coded badges. The same configured values drive tab visibility and catalog/matrix grouping.

### In-Silico Gene Lists (ISGL)

ISGL list types are also rendered as semantic badges. Standard list types (`snv`, `cnv`, `fusion`, `expression`, `pgx`) and ad-hoc list types (`adhoc_snv`, `adhoc_cnv`, `adhoc_fusion`, `adhoc_expression`, `adhoc_pgx`) use related colors so administrators can distinguish permanent curated lists from ad-hoc review lists.

---

## 3. Permissions Registry

For fine-grained security, Coyote3 utilizes a `resource:action[:scope]` permission string.

*   **Resource**: The entity being accessed (e.g., `sample`, `report`, `user`).
*   **Action**: The intent (e.g., `view`, `edit`, `download`).
*   **Scope**: (Optional) Limits the action to specific datasets (e.g., `own`, `all`).

*Example*: A user with `sample:edit:own` can only modify clinical metadata for samples they are explicitly assigned to.

---

## 4. System Ingestion and Audit

The **Ingest** workspace allows administrators to queue validated sample bundles and monitor background ingest behavior.
*   **Bulk Ingestion**: Monitor the status of high-throughput sequencer data arrivals.
*   **System Logs**: Accessible via the Admin Home, these logs provide a tamper-proof record of every sign-in and clinical action taken on the platform.

## Admin UI Conventions

| Pattern | Description |
| --- | --- |
| Glass cards | Admin list, edit, view, and utility panels use the same glass-card surface as clinical pages. |
| Read-only view pages | View actions render the same structured form layout as edit pages, but fields are read-only. |
| Forms | Normal admin workflows use typed forms, not JSON editors. |
| Permission selection | Permissions are grouped by category and shown as compact selectable rows with hover text for exact permission strings. |
| Dates | Tables use human relative dates for recent events and concise absolute dates for older events. |
| Notifications | Create, update, archive, delete, and error actions emit structured notifications. |
