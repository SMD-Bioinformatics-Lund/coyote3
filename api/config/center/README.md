# Center Configuration

This directory contains the deployer-editable Coyote3 configuration assets.
Edit these files before deployment when adapting Coyote3 to a laboratory or
section. Deploy API, worker, and scheduler with the same directory revision.

| File | Configure here |
| --- | --- |
| `contact.toml` | Center department, support channels, service hours, and any number of contact cards. |
| `clinical_vocabulary.toml` | Local assay groups, sequencing platforms, enabled local/LDAP providers, manifest file keys, and analysis-to-file bindings. |
| `collections.toml` | MongoDB database and physical collection names. |
| `assay_catalog.yaml` | Public assay catalog headings, narrative text, TAT, input material, and ISGL references. |
| `filter_flag_metadata.yaml` | User-facing VCF filter labels, severity, and tooltips. |

Repository identity, supported workflow semantics, authorization semantics, and
runtime code do not belong here. See the complete field-level protocol in
[`docs/operations/center_configuration_files.md`](../../../docs/operations/center_configuration_files.md)
and the vocabulary contract in
[`docs/operations/clinical_vocabulary.md`](../../../docs/operations/clinical_vocabulary.md).

`[authentication].providers` defines the center default. The optional
`AUTHENTICATION_PROVIDERS` environment variable overrides that default for one
deployment. LDAP configuration is checked when an LDAP login is attempted, not
during API startup; an enabled but unconfigured LDAP provider returns a clear
service-configuration error.
