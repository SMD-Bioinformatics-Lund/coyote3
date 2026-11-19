# Application Bootstrap Catalogs

<!-- badges:start -->
![Scope: Installation catalogs](https://img.shields.io/badge/Scope-Installation%20catalogs-4F46A5?style=flat)
<!-- badges:end -->

This directory contains server-owned application installation catalogs for an
empty Coyote4 database. The shared permission and role catalog belongs to core at
`core/src/coyote/config/catalogs/rbac`; the server reads that packaged catalog
when installing identity data. Atlas owns reference snapshots and the optional
Demo package owns synthetic workflows. Bootstrap is explicit; importing a package
does not write documents.

Software defaults are packaged separately in `core/src/coyote/config/`; physical
collection configuration belongs to `adapters/mongo/src/coyote_mongo/config/`. These files are loaded
by Python and are not MongoDB catalogs. Do not add duplicate seed documents or
copy these application-owned files into the external center directory.

## Catalogs

| Directory | Collections | Authority | First-deployment behavior |
| --- | --- | --- | --- |
| Core `config/catalogs/rbac/` | `permissions`, `roles` | Core release | Installed before the first local superuser is created. Bundled permissions and roles cannot be edited, deactivated or deleted through the UI. Centers can create their own roles. |
| `reference/` application catalogs | `assay_groups`, `query_rule_sets` | Coyote4 application release | Five biological groups and six group-scoped SNV publications on a fresh installation; query publications also receive immutable baseline revisions. |
| Atlas `data/reference/` | `hgnc_genes`, `vep_metadata`, `vep_diagrams` | Checked, versioned reference bundle in `coyote-atlas` | Explicit reference installation imports empty targets. Existing collections are preserved unless the operator explicitly requests the controlled bundled repair workflow. |
| Demo `data/demo_center/` and `data/clinical_workflows/` | Synthetic configuration and pipeline inputs | Optional `coyote-demo` package | Only the isolated demonstration workflow installs these resources; normal bootstrap does not load them. |

See [Installed defaults and demonstration configuration](../../../../../docs/administration/installed-defaults.md)
for the complete inventory, query conditions, demo filters and role responsibilities.

The compressed reference files use newline-delimited JSON. Compression keeps
the source checkout and container image smaller without changing the stored
MongoDB document shape.

## Empty-collection rule

`scripts/bootstrap/bootstrap_database.py` is the explicit first-deployment command. It
connects directly to the configured MongoDB URI before API, worker, or UI
services are started. On fresh application/identity targets it creates a named system
administrator and an emergency superuser with RBAC, then installs application
catalogs and selected Atlas HGNC/VEP references. Use `--skip-users`,
`--skip-application` and `--skip-knowledgebase` to disable modules subject to their
documented dependencies. Populated reference collections are preserved. Demonstrations
require the optional package and the separate
[isolated demo workflow](../../../../../docs/deployment/demo-installation.md).

Only the invocation that creates the initial accounts may add data without API login.
Existing deployments skip bootstrap completely, including missing modules. Later
additions and repairs use `install.sh data --api-url API_URL
--modules application knowledgebase`; add `--force` for selected bundled repairs.
The API service requires `admin`, `sys_admin` or `superuser`. The maintenance client
completes a required password change and signs in again before adding any data.
This prevents reference installation from silently mixing different HGNC/VEP snapshots
or replacing center-managed clinical configuration.

The operator supplies distinct usernames, email addresses, and temporary passwords
for the two accounts. No default credential is stored in this repository. Both
accounts are marked `system_managed` and must change their passwords at first sign-in.

Automated catalog creations use `created_by: "system"`. Authenticated maintenance
updates and audit events identify the operator.
Supported catalogs are marked `system_managed`, and document versions start
at `1`. Clinical rule content versions and revisions also start at `1`; their
synthetic review, publication, and lifecycle metadata use the administrator and
installation time. This metadata does not establish clinical approval. Generated
diagnosis definitions and associations start at version `1` with the same administrator.
Reference release identifiers remain unchanged. Existing database records and
immutable revision history are never reset by rerunning bootstrap.

Application upgrades use dedicated synchronization or release procedures:

- RBAC additions are applied with `scripts/identity/sync_rbac_catalog.py`.
- Query-rule roles and permissions are included in RBAC. Bootstrap combines
  `reference/query_rule_sets.seed.ndjson` with application-owned `reference/clinical_query_seed.toml`
  and installs version-one publications attributed to `system` during first
  installation or to the authenticated operator during maintenance.
  They are marked `system_installed`; installation does not imply independent review.
  `scripts/bootstrap/install_query_rules.py` plans and installs missing scopes in
  existing deployments without overwriting any existing scope or lifecycle history.
- HGNC and VEP releases are loaded as an intentional reference-data operation.
- `coyote-atlas update vep-metadata` downloads release-specific Ensembl website
  tables. The bundled VEP seed covers releases 98 through 116, with release 103
  preserved from the existing snapshot. Atlas `data/reference/vep_metadata.sources.json`
  records source commits and hashes; its `NOTICE.txt` records attribution.
  Seed updates produce a new review directory and regenerate its checked manifest;
  they do not modify installed package resources.
- Atlas `data/reference/vep_diagrams/` contains original binary images named by SHA-256.
  Keep these assets with the reference pack. Atlas checks their hashes and bootstrap
  installs them as BSON binary in `vep_diagrams`; VEP metadata contains only
  compact descriptors, never embedded base64 image strings.
- ASP, ASPC, and ISGL revisions are created through their managed versioned
  workflows.

## Excluded data

This directory must not contain users, credentials, samples, findings,
annotations, reports, patient identifiers, or center-specific clinical data.
Synthetic ingest and collection examples belong to `coyote-demo`, outside this
server package. Reference data and notices belong to `coyote-atlas`.
