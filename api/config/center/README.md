# Center Configuration

This directory contains complete example configuration files. Copy them once to
a center-owned directory outside the application checkout, or keep the center
configuration in a separate Git repository. Deploy a reviewed release through
`COYOTE3_CENTER_CONFIG_HOST_DIR`; application upgrades retain the same directory.

| File | Configure here |
| --- | --- |
| `contact.toml` | Center department, support channels, service hours, and any number of contact cards. |
| `clinical_vocabulary.toml` | Fusion evidence terms and optional DNA caller display metadata. Transcript selection belongs to the application; annotation wording belongs to reporting rules. |
| `filter_flag_metadata.yaml` | User-facing VCF filter labels, severity, and tooltips. |

API, worker, beat, and monitor mount the external directory read-only. Recreate
them together after a configuration release. Rebuild documentation when public
center identity changes. Physical collection mappings are application-owned in
`../collections.toml` and are not part of the external directory.

Repository identity, supported workflow semantics, authorization semantics, and
runtime code do not belong here. See the complete field-level protocol in
[`docs/deployment/center-configuration.md`](../../../docs/deployment/center-configuration.md)
and the vocabulary contract in
[`docs/administration/clinical-vocabulary.md`](../../../docs/administration/clinical-vocabulary.md).

The public assay catalog is not a mounted configuration file. Manage it in the
**Admin > Public Assay Catalog** builder. It is stored in the primary database;
JSON is available for complete-catalog or modality import/export only.

`../clinical_capabilities.toml` defines families (including WES), file keys,
analysis mappings, gene-list types, environments, supported fusion callers and
authentication providers. `../clinical_query_seed.toml` supplies application-owned
bootstrap criteria; live query policies are managed in the database editor.
`../clinical_query_defaults.toml` defines base SNV
evidence modes and population fields. Python loads these files from the application
package only; center files cannot override them. Do not copy either file into a
center configuration release.

The optional `AUTHENTICATION_PROVIDERS` environment variable selects supported providers for one
deployment. LDAP configuration is checked when an LDAP login is attempted, not
during API startup; an enabled but unconfigured LDAP provider returns a clear
service-configuration error.
