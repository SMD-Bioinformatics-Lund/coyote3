# Center Configuration

<!-- badges:start -->
![coyote-api: 1.0.0](https://img.shields.io/badge/coyote--api-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

This directory contains complete example configuration files. Copy them once to
a center-owned directory outside the application checkout, or keep the center
configuration in a separate Git repository. Deploy a reviewed release through
`COYOTE4_CENTER_CONFIG_HOST_DIR`; application upgrades retain the same directory.

| File | Configure here |
| --- | --- |
| `contact.toml` | Center department, support channels, service hours, and any number of contact cards. |
| `clinical_vocabulary.toml` | Fusion evidence terms and optional DNA caller display metadata. Transcript selection belongs to the application; annotation wording belongs to reporting rules. |
| `filter_flag_metadata.yaml` | VCF filter labels, severity, tooltips, and literal SNV flag choices. |
| `report_presentation.toml` (optional) | Plain-text messages for empty modern-report sections; loaded on each render. |

API, worker, beat, and monitor mount the external directory read-only. Recreate
them together after a configuration release. Rebuild documentation when public
center identity changes. Physical collection mappings are application-owned in
`adapters/mongo/src/coyote_mongo/config/collections.toml` in the repository and are
not part of the external directory.

Repository identity, supported workflow semantics, authorization semantics, and
runtime code do not belong here. See the complete field-level protocol in
[Center configuration](../../../../../../docs/deployment/center-configuration.md)
and the vocabulary contract in
[Clinical vocabulary](../../../../../../docs/administration/clinical-vocabulary.md).

The public assay catalog is not a mounted configuration file. Manage it in the
**Admin > Public Assay Catalog** builder. It is stored in the primary database;
JSON is available for complete-catalog or modality import/export only.

Core capabilities, analysis mappings, environments and factory query defaults
belong to `core/src/coyote/config/`, including `factory_defaults.toml` and typed
configuration modules. Application-owned query bootstrap criteria belong to
`api/src/coyote_api/bootstrap/catalogs/reference/clinical_query_seed.toml`.
Live query policies are managed in the database editor. These software-owned
definitions are separate from center files; do not copy them into a center
configuration release.

The optional `AUTHENTICATION_PROVIDERS` environment variable selects supported providers for one
deployment. LDAP configuration is checked when an LDAP login is attempted, not
during API startup; an enabled but unconfigured LDAP provider returns a clear
service-configuration error.
