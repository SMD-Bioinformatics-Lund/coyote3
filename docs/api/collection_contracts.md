# Collection Contracts

Generated from `api/contracts/schemas/registry.py`.

This is the canonical collection-key reference used by ingestion validation.

## Cross-collection relations

- `samples.assay` must match `asp_configs.assay_name` and `assay_specific_panels.asp_id`.
- `samples.profile` maps to ASPC lookup as `aspc_id = <assay>:<profile>`.
- `insilico_genelists.assays[]` and `assay_groups[]` must map to ASP/ASPC assay setup.
- `roles.permissions[]` must reference `permissions.permission_id`.
- `users.roles[]` must reference `roles.role_id`.
- `refseq_canonical.gene` should exist in `hgnc_genes.hgnc_symbol`.

## DNA vs RNA sample rules

- `omics_layer=DNA` allows only DNA file keys: `vcf_files`, `cnv`, `cov`, `biomarkers`, `transloc`.
- `omics_layer=RNA` allows only RNA file keys: `fusion_files`, `expression_path`, `classification_path`, `qc`.
- Mixed DNA+RNA file-key payloads are rejected by model validation.

## `annotation`

Required keys:
- `variant` (str)
- `gene` (str)
- `assay` (str)
- `subpanel` (str)
- `author` (str)
- `nomenclature` (Literal['p', 'g', 'c', 'f'])
- `transcript` (str)

Optional keys:
- `time_created` (datetime)
- `class_` (int | None)
- `text` (str | None)

## `asp_configs`

Required keys:
- `aspc_id` (str)
- `assay_name` (str)
- `environment` (Literal['production', 'development', 'testing', 'validation'])
- `asp_group` (str)
- `asp_category` (Literal['dna', 'rna'])
- `display_name` (str)
- `filters` (api.contracts.schemas.dna.DnaFiltersDoc | api.contracts.schemas.rna.RnaFiltersDoc)
- `reporting` (AspcReportingDoc)

Optional keys:
- `id_` (Any | None)
- `analysis_types` (list[str])
- `is_active` (bool)
- `description` (str | None)
- `reference_genome` (str | None)
- `platform` (str | None)
- `verification_samples` (dict[str, list[int]])
- `use_diagnosis_genelist` (bool)
- `query` (AspcQueryDoc)
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `asp_to_groups`

Required keys:
- `asp` (str)
- `asp_group` (str)

Optional keys:
- None

## `assay_specific_panels`

Required keys:
- `asp_id` (str)
- `assay_name` (str)
- `asp_group` (str)
- `asp_family` (Literal['panel-dna', 'panel-rna', 'wgs', 'wts'])
- `asp_category` (Literal['dna', 'rna'])
- `display_name` (str)

Optional keys:
- `id_` (Any | None)
- `description` (str | None)
- `expected_files` (list[str])
- `covered_genes` (list[str])
- `germline_genes` (list[str])
- `accredited` (bool)
- `kit_name` (str | None)
- `kit_type` (str | None)
- `kit_version` (str | None)
- `platform` (str | None)
- `read_mode` (str | None)
- `read_length` (int | None)
- `capture_method` (str | None)
- `target_region_size` (int | None)
- `is_active` (bool)
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `biomarkers`

Required keys:
- `SAMPLE_ID` (str)
- `name` (str)

Optional keys:
- `MSIS` (api.contracts.schemas.dna.BiomarkersMsiDoc | None)
- `MSIP` (api.contracts.schemas.dna.BiomarkersMsiDoc | None)
- `HRD` (api.contracts.schemas.dna.BiomarkersHrdDoc | None)

## `blacklist`

Required keys:
- `pos` (str)

Optional keys:
- `id_` (Any | None)
- `assay_group` (str | None)
- `in_normal_perc` (float | None)

## `brcaexchange`

Required keys:
- `id` (str)
- `chr` (str)
- `pos` (int)
- `ref` (str)
- `alt` (str)
- `chr38` (str)
- `pos38` (int)
- `ref38` (str)
- `alt38` (str)
- `enigma_clinsig` (str)
- `enigma_clinsig_refs` (str)
- `enigma_clinsig_comment` (str)

Optional keys:
- None

## `civic_genes`

Required keys:
- `gene_id` (int)
- `entrez_id` (int)
- `name` (str)
- `description` (str)
- `gene_civic_url` (str)
- `last_review_date` (datetime)

Optional keys:
- None

## `civic_variants`

Required keys:
- `variant_id` (int)
- `entrez_id` (int)
- `gene` (str)
- `variant` (str)
- `summary` (str)
- `variant_types` (str)
- `variant_groups` (str)
- `chromosome` (str)
- `start` (int)
- `stop` (int)
- `chromosome2` (str)
- `start2` (int)
- `stop2` (int)
- `reference_build` (str)
- `ensembl_version` (int)
- `representative_transcript` (str)
- `representative_transcript2` (str)
- `reference_bases` (str)
- `variant_bases` (str)
- `hgvs_expressions` (list[str])
- `civic_actionability_score` (float)
- `variant_civic_url` (str)
- `last_review_date` (datetime)

Optional keys:
- None

## `cnvs`

Required keys:
- `SAMPLE_ID` (str)
- `chr` (str)
- `start` (int)
- `end` (int)
- `size` (int)

Optional keys:
- `ratio` (float | None)
- `type` (str | None)
- `nprobes` (int)
- `genes` (list[api.contracts.schemas.dna.CnvGeneDoc])
- `callers` (list[str])

## `cosmic`

Required keys:
- `id` (str)
- `chr` (int)
- `start` (int)
- `end` (int)
- `cnt` (Dict[str, int])

Optional keys:
- None

## `dashboard_metrics`

Required keys:
- `payload` (DashboardPayloadDoc)
- `updated_at` (datetime)

Optional keys:
- None

## `fusions`

Required keys:
- `SAMPLE_ID` (str)
- `gene1` (str)
- `gene2` (str)
- `genes` (str)
- `calls` (List[api.contracts.schemas.rna.FusionCallDoc])

Optional keys:
- None

## `group_coverage`

Required keys:
- `SAMPLE_ID` (str)
- `sample` (str)

Optional keys:
- `genes` (Dict[str, api.contracts.schemas.dna.GeneCoverageDoc])

## `hgnc_genes`

Required keys:
- `hgnc_id` (str)
- `hgnc_symbol` (str)
- `gene_name` (str)
- `status` (str)
- `locus` (str)
- `locus_sortable` (str)
- `entrez_id` (int)
- `ensembl_gene_id` (str)
- `ensembl_mane_select` (str)
- `refseq_mane_select` (str)
- `chromosome` (str)
- `start` (int)
- `end` (int)
- `gene_gc_content` (float)
- `gene_description` (str)
- `ensembl_canonical` (bool)

Optional keys:
- `alias_symbol` (list[str])
- `alias_name` (list[str])
- `prev_symbol` (list[str])
- `prev_name` (list[str])
- `date_approved_reserved` (datetime.datetime | None)
- `date_symbol_changed` (datetime.datetime | None)
- `date_name_changed` (datetime.datetime | None)
- `date_modified` (datetime.datetime | None)
- `refseq_accession` (list[str])
- `cosmic` (list[str])
- `omim_id` (list[int])
- `pseudogene_org` (list[str])
- `imgt` (str | None)
- `lncrnadb` (str | None)
- `lncipedia` (str | None)
- `other_chromosome` (str | None)
- `gene_type` (list[str])
- `refseq_mane_plus_clinical` (list[str])
- `addtional_transcript_info` (dict[str, api.contracts.schemas.reference.HgncAdditionalTranscriptInfoDoc])

## `hpaexpr`

Required keys:
- `tid` (str)

Optional keys:
- `expr` (dict[str, float])

## `iarc_tp53`

Required keys:
- `id` (int)
- `var` (str)
- `polymorphism` (str)
- `cpg` (str)
- `splice` (str)
- `transactivation_class` (str)
- `AGVGD_class` (str)
- `residue_func` (str)
- `motif` (str)
- `structure_function_class` (str)
- `domain_func` (str)
- `n_somatic` (int)
- `n_germline` (int)

Optional keys:
- `topology_count` (int | None)

## `insilico_genelists`

Required keys:
- `isgl_id` (str)
- `name` (str)
- `displayname` (str)

Optional keys:
- `id_` (Any | None)
- `diagnosis` (list[str])
- `list_type` (list[str])
- `adhoc` (bool)
- `is_public` (bool)
- `is_active` (bool)
- `assay_groups` (list[str])
- `genes` (list[str])
- `assays` (list[str])
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `mane_select`

Required keys:
- `gene` (str)
- `enst` (str)
- `refseq` (str)
- `ensg` (str)

Optional keys:
- None

## `oncokb_actionable`

Required keys:
- `RefSeq` (str)
- `Alteration` (str)
- `Isoform` (str)
- `Drugs_s` (str)
- `Level` (str)
- `Cancer_Type` (str)
- `Entrez_Gene_ID` (int)
- `Hugo_Symbol` (str)
- `Protein_Change` (str)
- `PMIDs_for_drug` (str)

Optional keys:
- None

## `oncokb_genes`

Required keys:
- `name` (str)
- `description` (str)

Optional keys:
- None

## `panel_coverage`

Required keys:
- `SAMPLE_ID` (str)
- `sample` (str)

Optional keys:
- `genes` (Dict[str, api.contracts.schemas.dna.GeneCoverageDoc])

## `permissions`

Required keys:
- `permission_id` (str)
- `permission_name` (str)
- `label` (str)
- `category` (str)
- `tags` (list[str])

Optional keys:
- `id_` (Any | None)
- `description` (str | None)
- `is_active` (bool)
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `refseq_canonical`

Required keys:
- `gene` (str)
- `canonical` (str)

Optional keys:
- None

## `reported_variants`

Required keys:
- `report_id` (str)
- `sample_name` (str)
- `report_oid` (Any)
- `sample_oid` (Any)
- `var_oid` (Any)
- `annotation_oid` (Any)
- `annotation_text_oid` (Any)
- `sample_comment_oid` (Any)
- `simple_id` (str)
- `simple_id_hash` (str)
- `gene` (str)
- `transcript` (str)
- `hgvsc` (str)
- `hgvsp` (str)
- `variant` (str)
- `var_type` (str)
- `tier` (int)
- `created_by` (str)
- `created_on` (datetime)

Optional keys:
- None

## `rna_classification`

Required keys:
- `classifier_results` (list[api.contracts.schemas.rna.ClassifierResultDoc])
- `classifier_version` (str)
- `SAMPLE_ID` (str)

Optional keys:
- None

## `rna_expression`

Required keys:
- `sample` (list[api.contracts.schemas.rna.ExpressionSampleEntryDoc])
- `reference` (list[api.contracts.schemas.rna.ExpressionReferenceEntryDoc])
- `expression_version` (str)
- `SAMPLE_ID` (str)

Optional keys:
- None

## `rna_qc`

Required keys:
- `tot_reads` (int)
- `mapped_pct` (float)
- `multimap_pct` (float)
- `mismatch_pct` (float)
- `canon_splice` (int)
- `non_canon_splice` (int)
- `splice_ratio` (int)
- `genebody_cov` (List[int])
- `genebody_cov_slope` (float)
- `provider_genotypes` (Dict[str, str])
- `provider_called_genotypes` (int)
- `flendist` (int)
- `sample_id` (str)
- `SAMPLE_ID` (str)

Optional keys:
- None

## `roles`

Required keys:
- `role_id` (str)
- `name` (str)
- `label` (str)
- `color` (str)
- `level` (int | float)

Optional keys:
- `id_` (Any | None)
- `description` (str | None)
- `is_active` (bool)
- `permissions` (list[str])
- `deny_permissions` (list[str])
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `samples`

Required keys:
- `name` (str)
- `assay` (str)
- `subpanel` (str | None)
- `profile` (Literal['production', 'development', 'testing', 'validation'])
- `case_id` (str)
- `sample_no` (int)
- `sequencing_scope` (Literal['panel', 'wgs', 'wts'])
- `omics_layer` (Literal['dna', 'rna'])
- `pipeline` (str)
- `pipeline_version` (str)

Optional keys:
- `genome_build` (int | None)
- `vep_version` (str | None)
- `control_id` (str | None)
- `paired` (bool | None)
- `sequencing_technology` (str | None)
- `vcf_files` (str | None)
- `cnv` (str | None)
- `cnvprofile` (str | None)
- `cov` (str | None)
- `transloc` (str | None)
- `biomarkers` (str | None)
- `fusion_files` (str | None)
- `expression_path` (str | None)
- `classification_path` (str | None)
- `qc` (str | None)
- `uploaded_file_checksums` (dict[str, str])
- `filters` (api.contracts.schemas.dna.DnaFiltersDoc | api.contracts.schemas.rna.RnaFiltersDoc | None)
- `comments` (list[api.contracts.schemas.samples.SampleCommentDoc])
- `reports` (list[api.contracts.schemas.samples.SampleReportDoc])
- `case` (SampleCaseControlDoc)
- `control` (api.contracts.schemas.samples.SampleCaseControlDoc | None)
- `report_num` (int)
- `time_added` (datetime)

## `translocations`

Required keys:
- `SAMPLE_ID` (str)
- `CHROM` (str)
- `POS` (int)
- `REF` (str)
- `ALT` (str)
- `ID` (str)
- `GT` (list[api.contracts.schemas.dna.TranslocationGtDoc])
- `INFO` (list[api.contracts.schemas.dna.TranslocationInfoDoc])

Optional keys:
- `FILTER` (list[str])
- `FORMAT` (list[str])
- `QUAL` (float | None)

## `users`

Required keys:
- `email` (str)
- `username` (str)
- `firstname` (str)
- `lastname` (str)
- `fullname` (str)
- `job_title` (str)

Optional keys:
- `id_` (Any | None)
- `auth_type` (Literal['coyote3', 'ldap'] | None)
- `password` (str | None)
- `last_login` (datetime.datetime | None)
- `must_change_password` (bool)
- `password_updated_on` (datetime.datetime | None)
- `password_action_token_hash` (str | None)
- `password_action_purpose` (str | None)
- `password_action_expires_at` (datetime.datetime | None)
- `password_action_issued_at` (datetime.datetime | None)
- `password_action_issued_by` (str | None)
- `roles` (list[str])
- `environments` (list[Literal['production', 'development', 'testing', 'validation']])
- `assays` (list[str])
- `assay_groups` (list[str])
- `is_active` (bool)
- `permissions` (list[str])
- `deny_permissions` (list[str])
- `version` (int)
- `created_by` (str | None)
- `created_on` (datetime)
- `updated_by` (str | None)
- `updated_on` (datetime.datetime | None)
- `version_history` (list[api.contracts.schemas.base.VersionHistoryEntryDoc])

## `variants`

Required keys:
- `SAMPLE_ID` (str)
- `CHROM` (str)
- `POS` (int)
- `REF` (str)
- `ALT` (str)
- `ID` (str)
- `INFO` (VariantInfoDoc)
- `simple_id` (str)
- `simple_id_hash` (str)

Optional keys:
- `QUAL` (float | None)
- `FILTER` (list[str])
- `GT` (list[api.contracts.schemas.dna.VariantGtDoc])
- `gnomad_frequency` (float | None)
- `gnomad_max` (float | None)
- `exac_frequency` (float | None)
- `thousandG_frequency` (float | None)
- `variant_class` (str | None)
- `selected_csq_feature` (str | None)
- `genes` (list[str])
- `transcripts` (list[str])
- `HGVSc` (list[str])
- `HGVSp` (list[str])
- `cosmic_ids` (list[str])
- `dbsnp_id` (str | None)
- `pubmed_ids` (list[str])
- `hotspots` (list[dict[str, list[str]]])

## `vep_metadata`

Required keys:
- `vep_id` (str)
- `created_by` (str)
- `created_on` (datetime)
- `source` (str)
- `vc_translation_source` (str)
- `conseq_translation_source` (str)
- `db_info` (Dict[str, api.contracts.schemas.reference.VepDbInfoDoc])
- `variant_class_translations` (Dict[str, api.contracts.schemas.reference.VepVariantClassDoc])
- `conseq_translations` (Dict[str, api.contracts.schemas.reference.VepConsequenceDoc])
- `consequence_groups` (Dict[str, list[str]])

Optional keys:
- None
