# Collection inventory

<!-- GENERATED: scripts/docs/export_collection_dependencies.py -->

[How to read these relationships and plan a migration](README.md)

Every physical binding in `api/config/collections.toml` and every operational collection
is listed below. Database labels are logical services, not deployment database names.

| Namespace | Dependency reference | Binding |
| --- | --- | --- |
| `bam.samples` | [bam.samples](operations.md#bam-samples) | `bam_samples` |
| `identity.api_sessions` | [identity.api_sessions](identity.md#identity-api-sessions) | `api_sessions_collection` |
| `identity.audit_chain_heads` | [identity.audit_chain_heads](identity.md#identity-audit-chain-heads) | `OPERATIONAL_COLLECTIONS.audit_chain_heads` |
| `identity.audit_events` | [identity.audit_events](identity.md#identity-audit-events) | `audit_events_collection` |
| `identity.audit_outbox` | [identity.audit_outbox](identity.md#identity-audit-outbox) | `audit_outbox in the owning business database` |
| `identity.operational_audit_events` | [identity.operational_audit_events](identity.md#identity-operational-audit-events) | `OPERATIONAL_COLLECTIONS.operational_audit_events` |
| `identity.permissions` | [identity.permissions](identity.md#identity-permissions) | `permissions_collection` |
| `identity.roles` | [identity.roles](identity.md#identity-roles) | `roles_collection` |
| `identity.users` | [identity.users](identity.md#identity-users) | `users_collection` |
| `knowledgebase.brcaexchange` | [knowledgebase.brcaexchange](knowledgebase.md#knowledgebase-brcaexchange) | `brcaexchange_collection` |
| `knowledgebase.civic_genes` | [knowledgebase.civic_genes](knowledgebase.md#knowledgebase-civic-genes) | `civic_gene_collection` |
| `knowledgebase.civic_variants` | [knowledgebase.civic_variants](knowledgebase.md#knowledgebase-civic-variants) | `civic_variants_collection` |
| `knowledgebase.clinpgx_genes_public` | [knowledgebase.clinpgx_genes_public](knowledgebase.md#knowledgebase-clinpgx-genes-public) | `clinpgx_genes_public_collection` |
| `knowledgebase.cosmic` | [knowledgebase.cosmic](knowledgebase.md#knowledgebase-cosmic) | `cosmic_collection` |
| `knowledgebase.cosmic_actionability` | [knowledgebase.cosmic_actionability](knowledgebase.md#knowledgebase-cosmic-actionability) | `cosmic_actionability_collection` |
| `knowledgebase.cosmic_breakpoints` | [knowledgebase.cosmic_breakpoints](knowledgebase.md#knowledgebase-cosmic-breakpoints) | `cosmic_breakpoints_collection` |
| `knowledgebase.cosmic_cancer_gene_census` | [knowledgebase.cosmic_cancer_gene_census](knowledgebase.md#knowledgebase-cosmic-cancer-gene-census) | `cosmic_cgc_collection` |
| `knowledgebase.cosmic_census_gene_mutations` | [knowledgebase.cosmic_census_gene_mutations](knowledgebase.md#knowledgebase-cosmic-census-gene-mutations) | `cosmic_mutant_census_collection` |
| `knowledgebase.cosmic_cgc_hallmarks` | [knowledgebase.cosmic_cgc_hallmarks](knowledgebase.md#knowledgebase-cosmic-cgc-hallmarks) | `cosmic_cgc_hallmarks_collection` |
| `knowledgebase.cosmic_classification_papers` | [knowledgebase.cosmic_classification_papers](knowledgebase.md#knowledgebase-cosmic-classification-papers) | `cosmic_classification_paper_collection` |
| `knowledgebase.cosmic_classifications` | [knowledgebase.cosmic_classifications](knowledgebase.md#knowledgebase-cosmic-classifications) | `cosmic_classification_collection` |
| `knowledgebase.cosmic_copy_number` | [knowledgebase.cosmic_copy_number](knowledgebase.md#knowledgebase-cosmic-copy-number) | `cosmic_cna_collection` |
| `knowledgebase.cosmic_fusions` | [knowledgebase.cosmic_fusions](knowledgebase.md#knowledgebase-cosmic-fusions) | `cosmic_fusion_collection` |
| `knowledgebase.cosmic_gene_expression` | [knowledgebase.cosmic_gene_expression](knowledgebase.md#knowledgebase-cosmic-gene-expression) | `cosmic_expression_collection` |
| `knowledgebase.cosmic_genes` | [knowledgebase.cosmic_genes](knowledgebase.md#knowledgebase-cosmic-genes) | `cosmic_genes_collection` |
| `knowledgebase.cosmic_methylation` | [knowledgebase.cosmic_methylation](knowledgebase.md#knowledgebase-cosmic-methylation) | `cosmic_methylation_collection` |
| `knowledgebase.cosmic_mutation_census` | [knowledgebase.cosmic_mutation_census](knowledgebase.md#knowledgebase-cosmic-mutation-census) | `cosmic_mutation_census_collection` |
| `knowledgebase.cosmic_noncoding_variants` | [knowledgebase.cosmic_noncoding_variants](knowledgebase.md#knowledgebase-cosmic-noncoding-variants) | `cosmic_noncoding_collection` |
| `knowledgebase.cosmic_resistance_mutations` | [knowledgebase.cosmic_resistance_mutations](knowledgebase.md#knowledgebase-cosmic-resistance-mutations) | `cosmic_resistance_collection` |
| `knowledgebase.cosmic_signature_dbs` | [knowledgebase.cosmic_signature_dbs](knowledgebase.md#knowledgebase-cosmic-signature-dbs) | `cosmic_signature_dbs_collection` |
| `knowledgebase.cosmic_signature_sbs` | [knowledgebase.cosmic_signature_sbs](knowledgebase.md#knowledgebase-cosmic-signature-sbs) | `cosmic_signature_sbs_collection` |
| `knowledgebase.cosmic_signature_sv` | [knowledgebase.cosmic_signature_sv](knowledgebase.md#knowledgebase-cosmic-signature-sv) | `cosmic_signature_sv_collection` |
| `knowledgebase.cosmic_structural_variants` | [knowledgebase.cosmic_structural_variants](knowledgebase.md#knowledgebase-cosmic-structural-variants) | `cosmic_structural_collection` |
| `knowledgebase.cosmic_targeted_variants` | [knowledgebase.cosmic_targeted_variants](knowledgebase.md#knowledgebase-cosmic-targeted-variants) | `cosmic_targeted_collection` |
| `knowledgebase.cosmic_transcripts` | [knowledgebase.cosmic_transcripts](knowledgebase.md#knowledgebase-cosmic-transcripts) | `cosmic_transcripts_collection` |
| `knowledgebase.hgnc_genes` | [knowledgebase.hgnc_genes](knowledgebase.md#knowledgebase-hgnc-genes) | `hgnc_collection` |
| `knowledgebase.hpaexpr` | [knowledgebase.hpaexpr](knowledgebase.md#knowledgebase-hpaexpr) | `expression_collection` |
| `knowledgebase.iarc_tp53` | [knowledgebase.iarc_tp53](knowledgebase.md#knowledgebase-iarc-tp53) | `iarc_tp53_collection` |
| `knowledgebase.oncokb_actionable` | [knowledgebase.oncokb_actionable](knowledgebase.md#knowledgebase-oncokb-actionable) | `oncokb_actionable_collection` |
| `knowledgebase.oncokb_cancer_genes_public` | [knowledgebase.oncokb_cancer_genes_public](knowledgebase.md#knowledgebase-oncokb-cancer-genes-public) | `oncokb_cancer_genes_public_collection` |
| `knowledgebase.oncokb_genes` | [knowledgebase.oncokb_genes](knowledgebase.md#knowledgebase-oncokb-genes) | `oncokb_genes_collection` |
| `knowledgebase.oncokb_genes_public` | [knowledgebase.oncokb_genes_public](knowledgebase.md#knowledgebase-oncokb-genes-public) | `oncokb_genes_public_collection` |
| `knowledgebase.oncokb_public` | [knowledgebase.oncokb_public](knowledgebase.md#knowledgebase-oncokb-public) | `oncokb_public_collection` |
| `knowledgebase.onkokb` | [knowledgebase.onkokb](knowledgebase.md#knowledgebase-onkokb) | `oncokb_collection` |
| `knowledgebase.vep_diagrams` | [knowledgebase.vep_diagrams](knowledgebase.md#knowledgebase-vep-diagrams) | `vep_diagrams_collection` |
| `knowledgebase.vep_metadata` | [knowledgebase.vep_metadata](knowledgebase.md#knowledgebase-vep-metadata) | `vep_metadata_collection` |
| `knowledgebase.versions` | [knowledgebase.versions](knowledgebase.md#knowledgebase-versions) | `knowledgebase_versions_collection` |
| `primary.anno_vep` | [primary.anno_vep](clinical.md#primary-anno-vep) | `anno_vep_collection` |
| `primary.annotation` | [primary.annotation](clinical.md#primary-annotation) | `annotations_collection` |
| `primary.app_controls` | [primary.app_controls](operations.md#primary-app-controls) | `OPERATIONAL_COLLECTIONS.app_controls` |
| `primary.asp_configs` | [primary.asp_configs](configuration.md#primary-asp-configs) | `aspc_collection` |
| `primary.assay_groups` | [primary.assay_groups](configuration.md#primary-assay-groups) | `assay_groups_collection` |
| `primary.assay_setup_revisions` | [primary.assay_setup_revisions](workflows.md#primary-assay-setup-revisions) | `assay_setup_revisions_collection` |
| `primary.assay_setups` | [primary.assay_setups](workflows.md#primary-assay-setups) | `assay_setups_collection` |
| `primary.assay_specific_panels` | [primary.assay_specific_panels](configuration.md#primary-assay-specific-panels) | `asp_collection` |
| `primary.audit_outbox` | [primary.audit_outbox](operations.md#primary-audit-outbox) | `OPERATIONAL_COLLECTIONS.audit_outbox` |
| `primary.biomarkers` | [primary.biomarkers](clinical.md#primary-biomarkers) | `biomarkers_collection` |
| `primary.blacklist` | [primary.blacklist](configuration.md#primary-blacklist) | `blacklist_collection` |
| `primary.clinical_rule_revisions` | [primary.clinical_rule_revisions](workflows.md#primary-clinical-rule-revisions) | `clinical_rule_revisions_collection` |
| `primary.clinical_rule_sets` | [primary.clinical_rule_sets](workflows.md#primary-clinical-rule-sets) | `clinical_rule_sets_collection` |
| `primary.cnvs` | [primary.cnvs](clinical.md#primary-cnvs) | `cnvs_collection` |
| `primary.configuration_profiles` | [primary.configuration_profiles](workflows.md#primary-configuration-profiles) | `configuration_profiles_collection` |
| `primary.configuration_promotions` | [primary.configuration_promotions](workflows.md#primary-configuration-promotions) | `configuration_promotions_collection` |
| `primary.d4_coverage` | [primary.d4_coverage](clinical.md#primary-d4-coverage) | `d4_coverage_collection` |
| `primary.d4_coverage_blacklist` | [primary.d4_coverage_blacklist](configuration.md#primary-d4-coverage-blacklist) | `d4_coverage_blacklist_collection` |
| `primary.diagnoses` | [primary.diagnoses](configuration.md#primary-diagnoses) | `diagnoses_collection` |
| `primary.diagnosis_associations` | [primary.diagnosis_associations](configuration.md#primary-diagnosis-associations) | `diagnosis_associations_collection` |
| `primary.edit_leases` | [primary.edit_leases](operations.md#primary-edit-leases) | `OPERATIONAL_COLLECTIONS.edit_leases` |
| `primary.finding_comments` | [primary.finding_comments](clinical.md#primary-finding-comments) | `finding_comments_collection` |
| `primary.fusions` | [primary.fusions](clinical.md#primary-fusions) | `fusions_collection` |
| `primary.ingest_jobs` | [primary.ingest_jobs](operations.md#primary-ingest-jobs) | `ingest_jobs_collection` |
| `primary.insilico_genelists` | [primary.insilico_genelists](configuration.md#primary-insilico-genelists) | `insilico_genelist_collection` |
| `primary.notification_activity_progress` | [primary.notification_activity_progress](operations.md#primary-notification-activity-progress) | `OPERATIONAL_COLLECTIONS.notification_activity_progress` |
| `primary.notifications` | [primary.notifications](operations.md#primary-notifications) | `notifications_collection` |
| `primary.pgx` | [primary.pgx](clinical.md#primary-pgx) | `pgx_collection` |
| `primary.public_assay_catalog` | [primary.public_assay_catalog](workflows.md#primary-public-assay-catalog) | `public_assay_catalog_collection` |
| `primary.public_assay_catalog_revisions` | [primary.public_assay_catalog_revisions](workflows.md#primary-public-assay-catalog-revisions) | `public_assay_catalog_revisions_collection` |
| `primary.public_assay_catalog_versions` | [primary.public_assay_catalog_versions](workflows.md#primary-public-assay-catalog-versions) | `public_assay_catalog_versions_collection` |
| `primary.query_rule_revisions` | [primary.query_rule_revisions](workflows.md#primary-query-rule-revisions) | `query_rule_revisions_collection` |
| `primary.query_rule_sets` | [primary.query_rule_sets](workflows.md#primary-query-rule-sets) | `query_rule_sets_collection` |
| `primary.report_artifact_erasure` | [primary.report_artifact_erasure](operations.md#primary-report-artifact-erasure) | `OPERATIONAL_COLLECTIONS.report_artifact_erasure` |
| `primary.reported_variants` | [primary.reported_variants](clinical.md#primary-reported-variants) | `reported_variants_collection` |
| `primary.reports` | [primary.reports](clinical.md#primary-reports) | `reports_collection` |
| `primary.rna_classification` | [primary.rna_classification](clinical.md#primary-rna-classification) | `rna_classification_collection` |
| `primary.rna_expression` | [primary.rna_expression](clinical.md#primary-rna-expression) | `rna_expression_collection` |
| `primary.rna_qc` | [primary.rna_qc](clinical.md#primary-rna-qc) | `rna_qc_collection` |
| `primary.sample_comments` | [primary.sample_comments](clinical.md#primary-sample-comments) | `sample_comments_collection` |
| `primary.samples` | [primary.samples](clinical.md#primary-samples) | `samples_collection` |
| `primary.translocations` | [primary.translocations](clinical.md#primary-translocations) | `transloc_collection` |
| `primary.variants` | [primary.variants](clinical.md#primary-variants) | `variants_collection` |

## Contracts without a current physical binding

These registered schemas do not establish an active database collection binding:

- `asp_to_groups`: inspect its importer/consumer before scheduling migration; do not infer a database from the model name.
- `mane_select`: inspect its importer/consumer before scheduling migration; do not infer a database from the model name.
