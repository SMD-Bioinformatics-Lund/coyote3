"""Field presentation metadata for managed-resource forms."""

from __future__ import annotations

from typing import Any

from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote3.config.constants import (
    ALL_SAMPLE_FILE_KEYS,
    ASP_CATEGORY_OPTIONS,
    ASP_FAMILY_OPTIONS,
    AUTH_TYPE_OPTIONS,
    DIAGNOSIS_BASE_ID,
    DNA_ANALYSIS_TYPE_OPTIONS,
    ENVIRONMENT_OPTIONS,
    GENELIST_ADHOC_TYPE_OPTIONS,
    GENELIST_STANDARD_TYPE_OPTIONS,
    GENELIST_TYPE_OPTIONS,
    PLATFORM_OPTIONS,
    RNA_ANALYSIS_TYPE_OPTIONS,
    SAMPLE_FILE_KEYS,
)
from coyote3.config.contracts.governance import PERMISSION_CATALOG
from coyote3.config.sequencing import PLATFORM_CAPABILITIES

RESOURCE_EXTRA_FIELDS: dict[str, dict[str, dict[str, Any]]] = {
    "asp": {
        "platform": {
            "label": "Platform",
            "data_type": "text",
            "display_type": "input",
            "required": False,
        },
    },
    "aspc_dna": {
        "verification_samples": {
            "label": "Verification Samples",
            "data_type": "json",
            "display_type": "jsoneditor",
            "required": False,
            "default": {},
        },
    },
    "aspc_rna": {},
}

RESOURCE_FIELD_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "asp": {
        "asp_id": {
            "label": "Assay ID",
            "display_type": "input",
            "readonly_mode": ["edit"],
            "help": "Unique assay identifier. Existing IDs are retained because samples and configurations reference them.",
        },
        "igv": {
            "label": "IGV files",
            "data_type": "json",
            "display_type": "igv-config",
            "default": None,
        },
        "asp_group": {"display_type": "select", "options": []},
        "asp_family": {
            "display_type": "select",
            "options": list(ASP_FAMILY_OPTIONS),
            "help": "Select the sequencing family to set the modality and available analyses.",
        },
        "asp_category": {
            "display_type": "select",
            "readonly": True,
            "options": list(ASP_CATEGORY_OPTIONS),
            "options_by_field": {
                "field": "asp_family",
                "values": {
                    family: [category]
                    for family, category in CLINICAL_VOCABULARY.assay_family_categories.items()
                },
            },
            "help": "Determined by the sequencing family.",
        },
        "supported_analyses": {
            "label": "Supported analyses",
            "display_type": "checkbox-group",
            "options": list(
                dict.fromkeys((*DNA_ANALYSIS_TYPE_OPTIONS, *RNA_ANALYSIS_TYPE_OPTIONS))
            ),
            "options_by_field": {
                "field": "asp_family",
                "values": {
                    family: list(analyses)
                    for family, analyses in CLINICAL_VOCABULARY.analysis_types_by_family.items()
                },
            },
            "options_require_inputs": {
                "field": "expected_files",
                "values": {
                    analysis: list(
                        dict.fromkeys(
                            file_key
                            for bindings in CLINICAL_VOCABULARY.analysis_file_keys_by_omics.values()
                            for file_key in bindings.get(analysis, ())
                        )
                    )
                    for analysis in dict.fromkeys(
                        (*DNA_ANALYSIS_TYPE_OPTIONS, *RNA_ANALYSIS_TYPE_OPTIONS)
                    )
                },
            },
            "help": "Analyses supported by this assay. Configurations can enable a subset. Each selection must be supported by its family and accepted input files.",
        },
        "platform": {
            "display_type": "select",
            "options": list(PLATFORM_OPTIONS),
            "default": "illumina",
            "help": "Sequencing platform shown in the public catalog. Confirm for this assay.",
        },
        "read_mode": {
            "display_type": "select",
            "default": "PE",
            "options_by_field": {
                "field": "platform",
                "values": {
                    platform: list(capability["read_modes"])
                    for platform, capability in PLATFORM_CAPABILITIES.items()
                },
            },
            "help": "PE means paired-end; SE means single-end. Select a mode supported by the platform. It is not applicable to platforms without a selectable mode.",
        },
        "read_length": {
            "label": "Read length (bp)",
            "default": 150,
            "help": "Bases per read, not the combined length of a read pair. Confirm for this assay.",
        },
        "read_technology": {
            "readonly": True,
            "help": "Derived from the selected sequencing platform.",
        },
        "display_name": {"display_type": "input"},
        "description": {"display_type": "textarea"},
        "expected_files": {
            "display_type": "checkbox-group",
            "options": list(ALL_SAMPLE_FILE_KEYS),
            "category_options": {key: list(values) for key, values in SAMPLE_FILE_KEYS.items()},
            "options_by_field": {
                "field": "asp_category",
                "values": {key: list(values) for key, values in SAMPLE_FILE_KEYS.items()},
            },
            "help": "Files the assay is able to ingest. A declared file must be successfully loaded before the sample becomes ready.",
        },
        "required_files": {
            "display_type": "checkbox-group",
            "options": list(ALL_SAMPLE_FILE_KEYS),
            "category_options": {key: list(values) for key, values in SAMPLE_FILE_KEYS.items()},
            "options_from_field": "expected_files",
            "help": "Minimum files required for this assay. A manifest missing one of these files fails ingest.",
        },
        "covered_genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Assay-level targeted genes. Use canonical HGNC symbols and one symbol per entry.",
        },
        "germline_genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Genes for which the assay applies its configured germline review statement.",
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True, "hidden_mode": ["create"]},
        "created_on": {"readonly": True, "hidden_mode": ["create"]},
        "updated_by": {"readonly": True, "hidden_mode": ["create"]},
        "updated_on": {"readonly": True, "hidden_mode": ["create"]},
        "version": {"readonly": True, "hidden_mode": ["create"]},
        "supersedes_id": {
            "readonly": True,
            "hidden_mode": ["create"],
            "label": "Supersedes Record ID",
        },
        "retired_by": {"readonly": True, "hidden_mode": ["create"]},
        "retired_on": {"readonly": True, "hidden_mode": ["create"]},
        "retired_reason": {"readonly": True, "hidden_mode": ["create"]},
    },
    "aspc_dna": {
        "asp_id": {
            "display_type": "select",
            "label": "Assay",
            "dynamic_options": {"resource": "asp", "value": "asp_id", "label": "display_name"},
        },
        "diagnosis_id": {
            "display_type": "select",
            "label": "Diagnosis",
            "options": [DIAGNOSIS_BASE_ID],
            "default": DIAGNOSIS_BASE_ID,
            "help": "Select an active diagnosis registered under the selected assay. Use base for an assay-wide configuration.",
        },
        "aspc_id": {"readonly": True, "derive_from": ["asp_id", "diagnosis_id", "environment"]},
        "asp_group": {"readonly": True},
        "asp_category": {"readonly": True},
        "platform": {"readonly": True},
        "use_diagnosis_genelist": {
            "display_type": "checkbox",
            "label": "Automatically select diagnosis gene lists",
            "default": True,
        },
        "environment": {
            "display_type": "select",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "analysis_types": {
            "display_type": "checkbox-group",
            "options": list(DNA_ANALYSIS_TYPE_OPTIONS),
            "default": ["SNV", "CNV"],
        },
        "analysis_intents": {
            "display_type": "checkbox-group",
            "options": ["somatic", "germline"],
            "default": ["somatic"],
            "help": "Germline review is currently supported for SNV only. Select both to maintain separate somatic and germline SNV thresholds.",
        },
        "catalog": {
            "data_type": "json",
            "label": "Public Catalog",
            "display_type": "catalog-structured",
            "help": "Controls whether this active configuration is available in the public catalog. Catalog labels and descriptive content are managed in Admin > Assay Catalog.",
            "groups": [
                {
                    "title": "Visibility",
                    "fields": [
                        {
                            "key": "is_public",
                            "label": "Show In Public Catalog",
                            "type": "checkbox",
                            "default": True,
                        },
                    ],
                },
            ],
        },
        "filters": {
            "data_type": "json",
            "label": "Clinical Filter Profiles",
            "display_type": "filters-structured",
            "placeholder": "Configure only the enabled intent and analysis profiles",
            "groups": [
                {
                    "title": "Somatic SNV Thresholds",
                    "category": "Somatic SNV",
                    "requires_analysis": ["SNV"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.snv.min_alt_reads",
                            "label": "Min Alt Reads",
                            "type": "int",
                            "default": 5,
                        },
                        {
                            "key": "somatic.snv.min_depth",
                            "label": "Min Depth",
                            "type": "int",
                            "default": 100,
                        },
                        {
                            "key": "somatic.snv.min_freq",
                            "label": "Min AF",
                            "type": "float",
                            "default": 0.03,
                        },
                        {
                            "key": "somatic.snv.max_freq",
                            "label": "Max AF",
                            "type": "float",
                            "default": 1.0,
                        },
                        {
                            "key": "somatic.snv.max_control_freq",
                            "label": "Max Control AF",
                            "type": "float",
                            "default": 0.05,
                        },
                        {
                            "key": "somatic.snv.max_popfreq",
                            "label": "Max Population AF",
                            "type": "float",
                            "default": 0.01,
                        },
                    ],
                },
                {
                    "title": "Germline SNV Thresholds",
                    "category": "Germline SNV",
                    "requires_analysis": ["SNV"],
                    "requires_intent": ["germline"],
                    "fields": [
                        {
                            "key": "germline.snv.min_alt_reads",
                            "label": "Min Alt Reads",
                            "type": "int",
                            "default": 5,
                        },
                        {
                            "key": "germline.snv.min_depth",
                            "label": "Min Depth",
                            "type": "int",
                            "default": 100,
                        },
                        {
                            "key": "germline.snv.min_freq",
                            "label": "Min AF",
                            "type": "float",
                            "default": 0.03,
                        },
                        {
                            "key": "germline.snv.max_freq",
                            "label": "Max AF",
                            "type": "float",
                            "default": 1.0,
                        },
                        {
                            "key": "germline.snv.max_popfreq",
                            "label": "Max Population AF",
                            "type": "float",
                            "default": 0.01,
                        },
                    ],
                },
                {
                    "title": "Somatic CNV Thresholds",
                    "category": "Somatic CNV",
                    "requires_analysis": ["CNV"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.cnv.min_cnv_size",
                            "label": "Min CNV Size",
                            "type": "int",
                            "default": 100,
                        },
                        {
                            "key": "somatic.cnv.max_cnv_size",
                            "label": "Max CNV Size",
                            "type": "int",
                            "default": 1000000,
                        },
                        {
                            "key": "somatic.cnv.cnv_loss_cutoff",
                            "label": "CNV Loss Cutoff",
                            "type": "float",
                            "default": -0.3,
                        },
                        {
                            "key": "somatic.cnv.cnv_gain_cutoff",
                            "label": "CNV Gain Cutoff",
                            "type": "float",
                            "default": 0.3,
                        },
                    ],
                },
                {
                    "title": "Somatic SNV Scope And Consequences",
                    "category": "Somatic SNV",
                    "requires_analysis": ["SNV"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.snv.vep_consequences",
                            "label": "VEP Consequences",
                            "type": "checkbox-group",
                            "options": [],
                            "dynamic_options": {"resource": "vep_consequence_groups"},
                        },
                        {
                            "key": "somatic.snv.snvlists",
                            "label": "SNV Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                        },
                        {
                            "key": "somatic.snv.exclude_flags",
                            "label": "Excluded filter flags",
                            "type": "checkbox-group",
                            "options": [],
                        },
                    ],
                },
                {
                    "title": "Germline SNV Scope And Consequences",
                    "category": "Germline SNV",
                    "requires_analysis": ["SNV"],
                    "requires_intent": ["germline"],
                    "fields": [
                        {
                            "key": "germline.snv.vep_consequences",
                            "label": "VEP Consequences",
                            "type": "checkbox-group",
                            "options": [],
                            "dynamic_options": {"resource": "vep_consequence_groups"},
                        },
                        {
                            "key": "germline.snv.snvlists",
                            "label": "SNV Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                        },
                        {
                            "key": "germline.snv.exclude_flags",
                            "label": "Excluded filter flags",
                            "type": "checkbox-group",
                            "options": [],
                        },
                    ],
                },
                {
                    "title": "Somatic CNV Scope",
                    "category": "Somatic CNV",
                    "requires_analysis": ["CNV"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.cnv.cnvlists",
                            "label": "CNV Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                        },
                        {
                            "key": "somatic.cnv.cnveffects",
                            "label": "CNV Effects (gain/loss)",
                            "type": "checkbox-group",
                            "options": ["gain", "loss"],
                            "default": ["gain", "loss"],
                        },
                    ],
                },
                {
                    "title": "Somatic DNA Fusion And Translocation Scope",
                    "category": "Somatic DNA Fusion / Translocation",
                    "requires_analysis": ["TRANSLOCATION"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.translocation.fusionlists",
                            "label": "Fusion/Translocation Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                        },
                    ],
                },
                {
                    "title": "Somatic Coverage Thresholds",
                    "category": "Somatic Coverage",
                    "requires_analysis": ["COVERAGE"],
                    "requires_intent": ["somatic"],
                    "fields": [
                        {
                            "key": "somatic.coverage.warn_cov",
                            "label": "Warn Coverage",
                            "type": "int",
                            "default": 500,
                        },
                        {
                            "key": "somatic.coverage.error_cov",
                            "label": "Error Coverage",
                            "type": "int",
                            "default": 100,
                        },
                    ],
                },
            ],
        },
        "reporting": {
            "display_type": "reporting-structured",
            "groups": [
                {
                    "title": "Report Sections",
                    "fields": [
                        {
                            "key": "report_sections",
                            "label": "Report Sections",
                            "type": "checkbox-group",
                            "options": list(DNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["SNV", "CNV"],
                        },
                    ],
                },
                {
                    "title": "Report Text",
                    "fields": [
                        {
                            "key": "report_header",
                            "label": "Report Header",
                            "type": "text",
                            "default": "Coyote3 DNA Report",
                        },
                        {
                            "key": "report_method",
                            "label": "Report Method",
                            "type": "text",
                            "default": "NGS panel analysis",
                        },
                        {
                            "key": "report_description",
                            "label": "Report Description",
                            "type": "textarea",
                            "default": "DNA panel summary report",
                        },
                        {
                            "key": "language",
                            "label": "Reporting Language",
                            "type": "text",
                            "default": "sv",
                        },
                    ],
                },
                {
                    "title": "Report Paths",
                    "fields": [
                        {
                            "key": "plots_path",
                            "label": "Plots Path",
                            "type": "text",
                            "default": "/tmp",
                        },
                        {
                            "key": "report_folder",
                            "label": "Report Folder",
                            "type": "text",
                            "default": "reports",
                        },
                    ],
                },
            ],
        },
        "verification_samples": {"display_type": "jsoneditor"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True, "hidden_mode": ["create"]},
        "created_on": {"readonly": True, "hidden_mode": ["create"]},
        "updated_by": {"readonly": True, "hidden_mode": ["create"]},
        "updated_on": {"readonly": True, "hidden_mode": ["create"]},
        "version": {"readonly": True, "hidden_mode": ["create"]},
        "supersedes_id": {
            "readonly": True,
            "hidden_mode": ["create"],
            "label": "Supersedes Record ID",
        },
        "retired_by": {"readonly": True, "hidden_mode": ["create"]},
        "retired_on": {"readonly": True, "hidden_mode": ["create"]},
        "retired_reason": {"readonly": True, "hidden_mode": ["create"]},
    },
    "aspc_rna": {
        "analysis_intents": {
            "display_type": "checkbox-group",
            "options": ["somatic"],
            "default": ["somatic"],
            "help": "RNA configurations support somatic analysis.",
        },
        "asp_id": {
            "display_type": "select",
            "label": "Assay",
            "dynamic_options": {"resource": "asp", "value": "asp_id", "label": "display_name"},
        },
        "diagnosis_id": {
            "display_type": "select",
            "label": "Diagnosis",
            "options": [DIAGNOSIS_BASE_ID],
            "default": DIAGNOSIS_BASE_ID,
            "help": "Select an active diagnosis registered under the selected assay. Use base for an assay-wide configuration.",
        },
        "aspc_id": {"readonly": True, "derive_from": ["asp_id", "diagnosis_id", "environment"]},
        "asp_group": {"readonly": True},
        "asp_category": {"readonly": True},
        "platform": {"readonly": True},
        "use_diagnosis_genelist": {
            "display_type": "checkbox",
            "label": "Automatically select diagnosis gene lists",
            "default": True,
        },
        "environment": {
            "display_type": "select",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "analysis_types": {
            "display_type": "checkbox-group",
            "options": list(RNA_ANALYSIS_TYPE_OPTIONS),
            "default": ["FUSION"],
        },
        "catalog": {
            "data_type": "json",
            "label": "Public Catalog",
            "display_type": "catalog-structured",
            "help": "Controls whether this active configuration is available in the public catalog. Catalog labels and descriptive content are managed in Admin > Assay Catalog.",
            "groups": [
                {
                    "title": "Visibility",
                    "fields": [
                        {
                            "key": "is_public",
                            "label": "Show In Public Catalog",
                            "type": "checkbox",
                            "default": True,
                        },
                    ],
                },
            ],
        },
        "filters": {
            "data_type": "json",
            "label": "Clinical Filter Profiles",
            "display_type": "filters-structured",
            "placeholder": "Configure RNA thresholds and fusion_* strategy keys",
            "groups": [
                {
                    "title": "Somatic Fusion Thresholds",
                    "category": "Somatic RNA Fusion",
                    "requires_analysis": ["FUSION"],
                    "fields": [
                        {
                            "key": "somatic.fusion.min_spanning_reads",
                            "label": "Min Spanning Reads",
                            "type": "int",
                            "default": 5,
                        },
                        {
                            "key": "somatic.fusion.min_spanning_pairs",
                            "label": "Min Spanning Pairs",
                            "type": "int",
                            "default": 5,
                        },
                    ],
                },
                {
                    "title": "Somatic Fusion Scope",
                    "category": "Somatic RNA Fusion",
                    "requires_analysis": ["FUSION"],
                    "fields": [
                        {
                            "key": "somatic.fusion.fusion_callers",
                            "label": "Fusion Callers",
                            "type": "checkbox-group",
                            "options": list(CLINICAL_VOCABULARY.fusion_callers),
                            "default": ["arriba", "starfusion"],
                        },
                        {
                            "key": "somatic.fusion.fusion_descriptions",
                            "label": "Caller annotations",
                            "type": "checkbox-group",
                            "options": list(
                                dict.fromkeys(
                                    term
                                    for terms in CLINICAL_VOCABULARY.fusion_annotation_metadata().values()
                                    for term in terms
                                )
                            ),
                            "default": [],
                            "help": "Match RNA caller annotation terms. Empty selects all annotations.",
                        },
                        {
                            "key": "somatic.fusion.fusion_effects",
                            "label": "Fusion Effects",
                            "type": "checkbox-group",
                            "options": ["in-frame", "out-of-frame"],
                            "default": ["in-frame", "out-of-frame"],
                        },
                        {
                            "key": "somatic.fusion.fusionlists",
                            "label": "Fusion Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                        },
                    ],
                },
            ],
        },
        "reporting": {
            "display_type": "reporting-structured",
            "groups": [
                {
                    "title": "Report Sections",
                    "fields": [
                        {
                            "key": "report_sections",
                            "label": "Report Sections",
                            "type": "checkbox-group",
                            "options": list(RNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["FUSION"],
                        },
                    ],
                },
                {
                    "title": "Report Text",
                    "fields": [
                        {
                            "key": "report_header",
                            "label": "Report Header",
                            "type": "text",
                            "default": "Coyote3 RNA Report",
                        },
                        {
                            "key": "report_method",
                            "label": "Report Method",
                            "type": "text",
                            "default": "RNA fusion analysis",
                        },
                        {
                            "key": "report_description",
                            "label": "Report Description",
                            "type": "textarea",
                            "default": "RNA fusion summary report",
                        },
                        {
                            "key": "language",
                            "label": "Reporting Language",
                            "type": "text",
                            "default": "sv",
                        },
                    ],
                },
                {
                    "title": "Report Paths",
                    "fields": [
                        {
                            "key": "plots_path",
                            "label": "Plots Path",
                            "type": "text",
                            "default": "/tmp",
                        },
                        {
                            "key": "report_folder",
                            "label": "Report Folder",
                            "type": "text",
                            "default": "reports",
                        },
                    ],
                },
            ],
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True, "hidden_mode": ["create"]},
        "created_on": {"readonly": True, "hidden_mode": ["create"]},
        "updated_by": {"readonly": True, "hidden_mode": ["create"]},
        "updated_on": {"readonly": True, "hidden_mode": ["create"]},
        "version": {"readonly": True, "hidden_mode": ["create"]},
        "supersedes_id": {
            "readonly": True,
            "hidden_mode": ["create"],
            "label": "Supersedes Record ID",
        },
        "retired_by": {"readonly": True, "hidden_mode": ["create"]},
        "retired_on": {"readonly": True, "hidden_mode": ["create"]},
        "retired_reason": {"readonly": True, "hidden_mode": ["create"]},
    },
    "isgl": {
        "list_type": {
            "display_type": "checkbox-group",
            "options": list(GENELIST_TYPE_OPTIONS),
            "conditional_options": {
                "field": "adhoc",
                "truthy": list(GENELIST_ADHOC_TYPE_OPTIONS),
                "falsy": list(GENELIST_STANDARD_TYPE_OPTIONS),
            },
            "help": "Choose the clinical analysis domain. Ad-hoc lists expose only ad-hoc list types; curated lists expose only standard list types.",
        },
        "aliases": {
            "label": "Alternative names",
            "display_type": "textarea",
            "help": "Readable names for this gene list, separated by commas or new lines. Names are searchable; references always use isgl_id.",
        },
        "diagnosis": {
            "label": "Diagnoses",
            "display_type": "checkbox-group",
            "options": [],
            "default": [DIAGNOSIS_BASE_ID],
            "help": "Select registered diagnoses associated with the selected assays. Base means no named diagnosis.",
        },
        "asp_groups": {
            "display_type": "checkbox-group",
            "options": [],
            "help": "Select one or more assay groups to expose the assays that may use this gene list.",
        },
        "asp_ids": {
            "display_type": "checkbox-group",
            "help": "Select one or more assay groups first, then select the specific assays that may use this gene list.",
        },
        "genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Curated gene symbols for the selected clinical list type, one per entry.",
        },
        "adhoc": {
            "display_type": "checkbox",
            "label": "Ad-hoc list",
            "help": "Uses ad-hoc analysis list types instead of standard types. Ad-hoc lists are excluded from standard assay-configuration gene-list choices. Leave disabled for a routine curated list.",
        },
        "is_public": {
            "display_type": "checkbox",
            "label": "Public catalog visibility",
            "help": "Allows an active list and its genes to be exposed through public gene-list views. This does not publish an assay offering or select the list for clinical analysis.",
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True, "hidden_mode": ["create"]},
        "created_on": {"readonly": True, "hidden_mode": ["create"]},
        "updated_by": {"readonly": True, "hidden_mode": ["create"]},
        "updated_on": {"readonly": True, "hidden_mode": ["create"]},
        "version": {"readonly": True, "hidden_mode": ["create"]},
        "supersedes_id": {
            "readonly": True,
            "hidden_mode": ["create"],
            "label": "Supersedes Record ID",
        },
        "retired_by": {"readonly": True, "hidden_mode": ["create"]},
        "retired_on": {"readonly": True, "hidden_mode": ["create"]},
        "retired_reason": {"readonly": True, "hidden_mode": ["create"]},
    },
    "role": {
        "color": {
            "display_type": "color",
            "placeholder": "#4f46e5",
            "help": "Badge color stored as a six-digit hexadecimal value and applied immediately throughout the UI.",
        },
        "permissions": {"display_type": "checkbox-group"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "user": {
        "ui_settings": {
            "label": "Interface layouts",
            "display_type": "user-settings",
            "help": "Presentation preferences stored for this user and restored on later sessions.",
        },
        "auth_type": {"display_type": "checkbox-group", "options": list(AUTH_TYPE_OPTIONS)},
        "roles": {"display_type": "checkbox-group"},
        "username": {"readonly_mode": ["edit"]},
        "password": {
            "display_type": "password",
            "readonly_mode": ["edit"],
            "help": "Passwords are changed only through invite, reset, or authenticated password flows.",
        },
        "environments": {
            "display_type": "checkbox-group",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "asp_groups": {"display_type": "checkbox-group", "options": []},
        "asp_ids": {"display_type": "checkbox-group"},
        "must_change_password": {"display_type": "checkbox"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "permission": {
        "category": {"display_type": "select", "options": list(PERMISSION_CATALOG.categories)},
        "tags": {"display_type": "textarea"},
        "system_managed": {
            "display_type": "checkbox",
            "readonly": True,
            "default": False,
            "help": "Bundled application permissions are system-managed and assigned through roles.",
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
}

RESOURCE_SECTIONS: dict[str, list[tuple[str, list[str]]]] = {
    "asp": [
        (
            "assay identity",
            [
                "asp_id",
                "display_name",
                "asp_group",
                "asp_family",
                "asp_category",
                "platform",
                "read_mode",
                "read_length",
                "read_technology",
                "description",
            ],
        ),
        (
            "ingest contract",
            [
                "expected_files",
                "required_files",
                "supported_analyses",
            ],
        ),
        (
            "clinical gene scope",
            ["covered_genes", "germline_genes"],
        ),
        ("alignment viewer", ["igv"]),
        ("lifecycle", ["system_managed", "is_active"]),
        (
            "system metadata",
            [
                "version",
                "supersedes_id",
                "created_by",
                "created_on",
                "updated_by",
                "updated_on",
                "retired_by",
                "retired_on",
                "retired_reason",
            ],
        ),
    ],
    "aspc_dna": [
        (
            "configuration scope",
            [
                "aspc_id",
                "asp_id",
                "diagnosis_id",
                "environment",
                "asp_group",
                "asp_category",
                "platform",
            ],
        ),
        ("enabled analysis", ["analysis_types", "analysis_intents"]),
        ("analytical filters", ["filters"]),
        ("clinical reporting", ["reporting"]),
        ("public catalog", ["catalog"]),
        ("verification", ["verification_samples"]),
        ("lifecycle", ["system_managed", "is_active"]),
        (
            "system metadata",
            [
                "version",
                "supersedes_id",
                "created_by",
                "created_on",
                "updated_by",
                "updated_on",
                "retired_by",
                "retired_on",
                "retired_reason",
            ],
        ),
    ],
    "aspc_rna": [
        (
            "configuration scope",
            [
                "aspc_id",
                "asp_id",
                "diagnosis_id",
                "environment",
                "asp_group",
                "asp_category",
                "platform",
            ],
        ),
        ("enabled analysis", ["analysis_types", "analysis_intents"]),
        ("analytical filters", ["filters"]),
        ("clinical reporting", ["reporting"]),
        ("public catalog", ["catalog"]),
        ("lifecycle", ["system_managed", "is_active"]),
        (
            "system metadata",
            [
                "version",
                "supersedes_id",
                "created_by",
                "created_on",
                "updated_by",
                "updated_on",
                "retired_by",
                "retired_on",
                "retired_reason",
            ],
        ),
    ],
    "isgl": [
        ("list identity", ["isgl_id", "name", "displayname", "aliases", "list_type"]),
        ("clinical scope", ["asp_groups", "asp_ids", "diagnosis"]),
        ("curated gene content", ["genes"]),
        ("availability", ["adhoc", "is_public", "system_managed", "is_active"]),
        (
            "system metadata",
            [
                "version",
                "supersedes_id",
                "created_by",
                "created_on",
                "updated_by",
                "updated_on",
                "retired_by",
                "retired_on",
                "retired_reason",
            ],
        ),
    ],
    "user": [
        ("identity", ["firstname", "lastname", "fullname", "username", "email", "job_title"]),
        ("auth", ["auth_type", "password", "must_change_password"]),
        ("role_access", ["roles"]),
        ("scope", ["environments", "asp_groups", "asp_ids"]),
        ("user settings", ["ui_settings"]),
        ("status", ["system_managed", "is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "role": [
        ("identity", ["name", "label", "description", "color", "level"]),
        ("permissions", ["permissions"]),
        ("status", ["system_managed", "is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "permission": [
        ("identity", ["permission_id", "label", "category", "description", "tags"]),
        ("status", ["system_managed", "is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
}

RESOURCE_EXCLUDED_FIELDS: dict[str, set[str]] = {
    "asp": set(),
    "aspc_dna": {
        "id_",
        "clinical_rule_base",
        "profile_sources",
        "profile_overrides",
        "template_release",
        "promotion",
        "assay_resource_release",
        "gene_list_release",
        "query_policy_release",
        "clinical_rule_release",
    },
    "aspc_rna": {
        "id_",
        "clinical_rule_base",
        "profile_sources",
        "profile_overrides",
        "template_release",
        "promotion",
        "assay_resource_release",
        "gene_list_release",
        "query_policy_release",
        "clinical_rule_release",
    },
    "isgl": set(),
    "user": {
        "password_updated_on",
        "password_action_token_hash",
        "password_action_purpose",
        "password_action_expires_at",
        "password_action_issued_at",
        "password_action_issued_by",
    },
    "role": {"role_id"},
}
