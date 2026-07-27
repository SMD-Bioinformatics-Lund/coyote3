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

When `clinical_vocabulary.toml` enables `ldap` under
`[authentication].providers`, the deployment environment must supply a valid
`LDAP_HOST`. A local-only centre should remove `ldap` from that list; the API
will then not initialize an LDAP client.
