"""Common DNA reporting/variant transformation helpers."""

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from pprint import pformat
from typing import Any, Dict, List, Tuple

from api.application.interpretation.annotation_enrichment import (
    add_global_annotations as shared_add_global_annotations,
)
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.service import rendered_summary
from api.config.constants import primary_analysis_file_key
from api.config.database_versions import sample_vep_version
from api.domain.common.assay_filters import (
    get_assay_genelist_names,
    get_sample_effective_genes,
)
from api.domain.common.reporting import (
    TIER_DESC,
    TIER_SHORT_DESC,
    VARIANT_CLASS_TRANSLATION,
    get_plot,
    get_report_header,
)
from api.domain.common.sample_filters import (
    merge_filter_defaults,
    merged_dna_cnv_filters,
    merged_dna_variant_filters,
)
from api.domain.core.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
)
from api.domain.core.dna.dna_filters import (
    get_filter_conseq_terms as shared_get_filter_conseq_terms,
)
from api.domain.core.dna.notation import one_letter_p, standard_hgvs
from api.domain.core.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)
from api.domain.core.dna.varqueries import build_query
from api.domain.core.reporting.report_paths import (
    get_report_timestamp as shared_get_report_timestamp,
)

logger = logging.getLogger(__name__)


def _sample_file_path(sample: dict[str, Any], key: str) -> str:
    """Return a sample file path from the canonical nested file contract."""
    file_doc = (
        (sample.get("files") or {}).get(key) if isinstance(sample.get("files"), dict) else None
    )
    if isinstance(file_doc, dict):
        return str(file_doc.get("path") or "")
    if isinstance(file_doc, str):
        return file_doc
    return str(sample.get(key) or "")


def hotspot_variant(variants: list) -> list[dict]:
    """
    Return variants with HOTSPOT keys hydrated from hotspot payloads.
    """
    hotspots = []
    for variant in variants:
        hotspot_dict = variant.get("hotspots", [{}])[0]
        if hotspot_dict:
            for hotspot_key, hotspot_elem in hotspot_dict.items():
                if any("COS" in elem for elem in hotspot_elem):
                    variant.setdefault("INFO", {}).setdefault("HOTSPOT", []).append(hotspot_key)
        hotspots.append(variant)
    return hotspots


def filter_variants_for_report(variants: list, filter_genes: list, assay: str) -> list:
    """
    Filter and sort variants included in report output.
    """
    return sorted(
        [
            var
            for var in variants
            if (
                var.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL") in filter_genes
                or len(filter_genes) == 0
            )
            and not var.get("blacklist")
            and var.get("classification")
            and var.get("classification", {}).get("class", 0) not in [4, 999]
            and not (
                (assay == "gmsonco" and var.get("classification", {}).get("class", 0) == 3)
                if assay != "tumwgs"
                else False
            )
        ],
        key=lambda var: var.get("classification", {}).get("class", 0),
    )


def sort_by_class_and_af(data: list[dict]) -> list[dict]:
    """
    Sort by class ascending and AF descending.
    """
    return sorted(data, key=lambda d: (d["class"], -d["af"]))


def get_simple_variants_for_report(variants: list, assay_config: dict) -> list:
    """
    Generate simplified variant rows for DNA report rendering.
    """
    translation = VARIANT_CLASS_TRANSLATION
    class_short_desc_list = TIER_SHORT_DESC
    class_long_desc_list = TIER_DESC

    simple_variants = []

    for var in variants:
        cdna = ""
        protein_changes = []
        af = None

        indel_size = len(var.get("ALT")) - len(var.get("REF"))
        selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
        var_type = "snv"
        variant_class = var.get("classification", {}).get("class")
        if indel_size > 20 or indel_size < -20:
            var_type = "indel"

            if indel_size < 0:
                variant = cdna = f"{abs(indel_size)}bp DEL"
            else:
                variant = cdna = f"{indel_size}bp INS"
        elif selected_csq.get("HGVSc"):
            variant = cdna = selected_csq.get("HGVSc")
        elif var.get("INFO", {}).get("SVTYPE"):
            var_type = "sv"
            sv_type = var.get("INFO", {}).get("SVTYPE")
            variant = cdna = (
                f"{var.get('INFO', {}).get('SVLEN')}bp {translation.get(sv_type, sv_type)}"
            )
        else:
            variant = "?"

        if selected_csq.get("HGVSp", None):
            if -20 <= indel_size <= 20:
                var_type = "snv"
                variant = standard_hgvs(one_letter_p(selected_csq.get("HGVSp")))
                protein_changes = [
                    standard_hgvs(one_letter_p(selected_csq.get("HGVSp"))),
                    standard_hgvs(selected_csq.get("HGVSp")),
                ]
            else:
                protein_changes = [
                    one_letter_p(selected_csq.get("HGVSp")),
                    selected_csq.get("HGVSp"),
                ]

        if variant_class in class_short_desc_list:
            variant_class_short = class_short_desc_list[variant_class]
        else:
            variant_class_short = "-"

        if variant_class in class_short_desc_list:
            variant_class_long = class_long_desc_list[variant_class]
        else:
            variant_class_long = "-"

        if var.get("INFO", {}).get("MYELOID_GERMLINE") == 1 or "GERMLINE" in var.get("FILTER", []):
            class_type = "Konstitutionell"
        else:
            class_type = "Somatisk"

        all_conseq = selected_csq.get("Consequence", [])
        consequence = ""
        if all_conseq and isinstance(all_conseq, list):
            for c in all_conseq:
                if c in translation:
                    consequence = translation[c]
                    break
                else:
                    consequence = c
        elif all_conseq and isinstance(all_conseq, str):
            for c in all_conseq.split("&"):
                if c in translation:
                    consequence = translation[c]
                    break
                else:
                    consequence = c

        if var.get("INFO", {}).get("SVTYPE") and selected_csq.get("SYMBOL") == "FLT3":
            af = "N/A"
        else:
            for gt in var.get("GT", []):
                if gt.get("type") == "case":
                    af = gt.get("AF")
                    break

        exon_raw = selected_csq.get("EXON") or ""
        exons = [
            e for e in (exon_raw.split("/") if isinstance(exon_raw, str) else []) if e and e.strip()
        ]
        intron_raw = selected_csq.get("INTRON") or ""
        introns = [
            i
            for i in (intron_raw.split("/") if isinstance(intron_raw, str) else [])
            if i and i.strip()
        ]

        simple_variants.append(
            {
                "chr": var.get("CHROM"),
                "pos": var.get("POS"),
                "ref": var.get("REF"),
                "alt": var.get("ALT"),
                "variant": variant,
                "indel_size": indel_size,
                "af": af,
                "symbol": selected_csq.get("SYMBOL"),
                "exon": exons,
                "intron": introns,
                "class": variant_class,
                "class_short_desc": variant_class_short,
                "class_long_desc": variant_class_long,
                "hotspot": var.get("INFO", {}).get("HOTSPOT"),
                "var_type": var_type,
                "class_type": class_type,
                "var_class": var.get("variant_class", ""),
                "feature": selected_csq.get("Feature", ""),
                "consequence": consequence,
                "cdna": cdna,
                "protein_changes": protein_changes,
                "global_annotations": var.get("global_annotations", []),
                "annotations_interesting": var.get("annotations_interesting", []),
                "comments": var.get("comments", []),
            }
        )
    return simple_variants


def _ensure_sample_filters(sample: dict, assay_config: dict) -> tuple[dict, dict]:
    """Return sample filters completed from its resolved ASPC defaults."""
    sample = deepcopy(sample)
    sample_filters = merge_filter_defaults(
        sample.get("filters"),
        assay_config.get("filters"),
        omics_layer=str(sample.get("omics_layer") or "dna"),
        analysis_intents=sample.get("analysis_intents"),
    )
    sample["filters"] = sample_filters
    return sample, sample_filters


def _resolve_sample_vep_version(sample: dict) -> str:
    """Return the sample VEP version used for report consequence mapping."""
    normalized = sample_vep_version(sample)
    if not normalized:
        raise ValueError("sample.database_versions.vep is required for DNA report generation")
    return normalized


def _normalize_dna_report_sections(sections: list[str] | None) -> list[str]:
    """Normalize DNA report-section toggles to supported rendered sections."""
    raw = [str(value).strip().upper() for value in (sections or []) if str(value).strip()]
    normalized: list[str] = []
    include_biomarker = False
    for value in raw:
        if value in {"BIOMARKER", "TMB", "PGX"}:
            include_biomarker = True
            continue
        if value not in normalized:
            normalized.append(value)
    if include_biomarker:
        normalized.append("BIOMARKER")
    return normalized


def _resolve_filter_genes(
    sample: dict,
    sample_filters: dict,
    assay_panel_doc: dict,
    *,
    gene_list_repository,
) -> tuple[dict, list]:
    """Resolve gene coverage map and effective report filter genes."""
    snv_filters = merged_dna_variant_filters(sample_filters)
    checked_snvlists = snv_filters.get("snvlists", [])
    checked_snvlists_genes_dict: dict[str, Any] = gene_list_repository.get_isgl_by_ids(
        checked_snvlists
    )
    return get_sample_effective_genes(sample, assay_panel_doc, checked_snvlists_genes_dict)


def _resolve_cnv_filter_genes(
    sample: dict,
    sample_filters: dict,
    assay_panel_doc: dict,
    *,
    gene_list_repository,
) -> list[str]:
    """Resolve effective CNV report filter genes from selected CNV lists."""
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    checked_cnvlists = cnv_filters.get("cnvlists", [])
    checked_cnvlists_genes_dict: dict[str, Any] = gene_list_repository.get_isgl_by_ids(
        checked_cnvlists
    )
    _genes_covered_in_panel, filter_genes = get_sample_effective_genes(
        sample,
        assay_panel_doc,
        checked_cnvlists_genes_dict,
        target="cnv",
    )
    return filter_genes


def _filter_cnvs_for_report(
    cnvs: list[dict],
    *,
    sample_filters: dict,
    filter_genes: list[str],
) -> list[dict]:
    """Apply CNV effect and gene-list filters to report-included CNVs."""
    filtered_cnvs = list(cnvs)
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    filter_cnveffects = create_cnveffectlist(cnv_filters.get("cnveffects", []))
    if filter_cnveffects:
        filtered_cnvs = cnvtype_variant(filtered_cnvs, filter_cnveffects)
    if filter_genes:
        filter_genes_set = set(filter_genes)
        filtered_cnvs = [
            cnv
            for cnv in filtered_cnvs
            if any((gene or {}).get("gene") in filter_genes_set for gene in cnv.get("genes", []))
        ]
    return cnv_organizegenes(filtered_cnvs)


def _resolve_disp_positions(sample: dict, assay_config: dict) -> list:
    """Resolve optional verification display coordinates for the current sample."""
    disp_pos = []
    verification_samples = assay_config.get("verification_samples")
    if verification_samples and sample["name"] in verification_samples:
        disp_pos = verification_samples[sample["name"]]
    return disp_pos


def _build_variant_query(
    assay_group: str,
    sample: dict,
    sample_filters: dict,
    filter_conseq: list,
    filter_genes: list,
    disp_pos: list,
    intent: str = "somatic",
) -> dict:
    """Build variant lookup query payload for report preparation."""
    snv_filters = merged_dna_variant_filters(sample_filters, intent=intent)
    return build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": snv_filters["max_freq"],
            "min_freq": snv_filters["min_freq"],
            "max_control_freq": snv_filters.get("max_control_freq", 1.0),
            "min_depth": snv_filters["min_depth"],
            "min_alt_reads": snv_filters["min_alt_reads"],
            "max_popfreq": snv_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
            "fp": {"$ne": True},
            "irrelevant": {"$ne": True},
        },
        intent=intent,
    )


def _build_snapshot_rows(
    variants: list[dict],
    assay_group: str,
    subpanel: str | None,
    latest_sample_comment: dict | None,
    intent: str = "somatic",
) -> list[dict[str, Any]]:
    """Build snapshot rows for reported-variant persistence."""
    now_utc = datetime.now(timezone.utc)
    snapshot_rows: list[dict[str, Any]] = []
    for v in variants:
        annotations_interesting = v.get("annotations_interesting", {})
        annotations_interesting_assay_specific = (
            annotations_interesting.get(assay_group)
            or annotations_interesting.get(f"{assay_group}:{subpanel}")
            or {}
        )
        sel = (v.get("INFO", {}) or {}).get("selected_CSQ", {}) or {}
        simple_id = normalize_simple_id(v.get("simple_id"))
        simple_id_hash = v.get("simple_id_hash") or (
            build_simple_id_hash_from_simple_id(simple_id) if simple_id else None
        )
        snapshot_rows.append(
            {
                "var_oid": v.get("_id"),
                "annotation_oid": v.get("classification", {}).get("_id", None),
                "annotation_text_oid": annotations_interesting_assay_specific.get("_id", None),
                "sample_comment_oid": (
                    latest_sample_comment.get("_id") if latest_sample_comment else None
                ),
                "var_type": v.get("variant_class"),
                "analysis_intent": intent,
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "tier": v.get("classification", {}).get("class"),
                "gene": sel.get("SYMBOL") or (v.get("gene") or None),
                "transcript": sel.get("Feature") or v.get("selected_csq_feature"),
                "hgvsp": sel.get("HGVSp") or v.get("hgvsp"),
                "hgvsc": sel.get("HGVSc") or v.get("hgvsc"),
                "variant": v.get("classification", {}).get("variant"),
                "created_on": now_utc,
            }
        )
    return snapshot_rows


def build_dna_report_payload(
    sample: dict,
    assay_config: dict,
    save: int = 0,
    include_snapshot: bool = False,
    *,
    assay_panel_repository,
    gene_list_repository,
    variant_repository,
    blacklist_repository,
    sample_repository,
    copy_number_variant_repository,
    biomarker_repository,
    translocation_repository,
    vep_metadata_repository,
    annotation_repository,
    clinical_rule_service=None,
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Build DNA report template context and optional reported-variant snapshot rows.
    """
    sample_assay = sample.get("asp_id")
    assay_group: str = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel_id")
    report_sections = _normalize_dna_report_sections(
        assay_config.get("reporting", {}).get("report_sections", [])
    )
    report_sections_data: Dict[str, Any] = {}

    logger.debug("Assay group: %s - DNA config: %s", assay_group, pformat(report_sections))
    logger.debug("Assay group: %s - Subpanel: %s", assay_group, subpanel)

    assay_panel_doc = assay_panel_repository.get_asp(asp_name=sample_assay)
    # Preserve assay genelist hydration step for parity with historical report flow.
    _insilico_panel_genelists = list(
        gene_list_repository.get_isgl_by_asp(sample_assay, is_active=True) or []
    )
    _all_panel_genelist_names = get_assay_genelist_names(_insilico_panel_genelists)

    sample, sample_filters = _ensure_sample_filters(sample, assay_config)
    genes_covered_in_panel, filter_genes = _resolve_filter_genes(
        sample=sample,
        sample_filters=sample_filters,
        assay_panel_doc=assay_panel_doc,
        gene_list_repository=gene_list_repository,
    )
    sample_vep_version = _resolve_sample_vep_version(sample)
    conseq_terms_mapper = vep_metadata_repository.get_consequence_group_map(sample_vep_version)
    snv_filters = merged_dna_variant_filters(sample_filters)
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    filter_conseq = shared_get_filter_conseq_terms(
        snv_filters.get("vep_consequences", []),
        conseq_terms_mapper,
    )
    disp_pos = _resolve_disp_positions(sample, assay_config)

    query = _build_variant_query(
        assay_group=assay_group,
        sample=sample,
        sample_filters=sample_filters,
        filter_conseq=filter_conseq,
        filter_genes=filter_genes,
        disp_pos=disp_pos,
    )

    variants = list(variant_repository.get_case_variants(query) or [])
    variants = blacklist_repository.add_blacklist_data(variants, assay=assay_group)

    variants, tiered_variants = shared_add_global_annotations(
        variants, assay_group, subpanel, annotation_repository=annotation_repository
    )
    variants = hotspot_variant(variants)
    variants = filter_variants_for_report(variants, filter_genes, assay_group)

    latest_sample_comment = sample_repository.get_latest_sample_comment(
        sample_id=str(sample["_id"])
    )

    snapshot_rows: List[Dict[str, Any]] = []
    if include_snapshot:
        snapshot_rows = _build_snapshot_rows(
            variants=variants,
            assay_group=assay_group,
            subpanel=subpanel,
            latest_sample_comment=latest_sample_comment,
        )

    variants_simple = get_simple_variants_for_report(variants, assay_config)
    report_sections_data["snvs"] = sort_by_class_and_af(variants_simple)
    rule_sections_data: Dict[str, Any] = {"snvs": variants}

    germline_variants: list[dict[str, Any]] = []
    if "germline" in set(sample.get("analysis_intents") or []):
        germline_filters = merged_dna_variant_filters(sample_filters, intent="germline")
        germline_consequences = shared_get_filter_conseq_terms(
            germline_filters.get("vep_consequences", []), conseq_terms_mapper
        )
        germline_query = _build_variant_query(
            assay_group=assay_group,
            sample=sample,
            sample_filters=sample_filters,
            filter_conseq=germline_consequences,
            filter_genes=filter_genes,
            disp_pos=disp_pos,
            intent="germline",
        )
        germline_variants = list(variant_repository.get_case_variants(germline_query) or [])
        germline_variants = blacklist_repository.add_blacklist_data(
            germline_variants, assay=assay_group
        )
        germline_variants, _ = shared_add_global_annotations(
            germline_variants, assay_group, subpanel, annotation_repository=annotation_repository
        )
        germline_variants = hotspot_variant(germline_variants)
        germline_variants = filter_variants_for_report(germline_variants, filter_genes, assay_group)
        if include_snapshot:
            snapshot_rows.extend(
                _build_snapshot_rows(
                    variants=germline_variants,
                    assay_group=assay_group,
                    subpanel=subpanel,
                    latest_sample_comment=latest_sample_comment,
                    intent="germline",
                )
            )
        report_sections_data["germline_snvs"] = sort_by_class_and_af(
            get_simple_variants_for_report(germline_variants, assay_config)
        )

    if "CNV" in report_sections:
        cnv_filter_genes = _resolve_cnv_filter_genes(
            sample,
            sample_filters,
            assay_panel_doc,
            gene_list_repository=gene_list_repository,
        )
        interesting_cnvs = list(
            copy_number_variant_repository.get_interesting_sample_cnvs(sample_id=str(sample["_id"]))
            or []
        )
        report_sections_data["cnvs"] = _filter_cnvs_for_report(
            interesting_cnvs,
            sample_filters=sample_filters,
            filter_genes=cnv_filter_genes,
        )
        rule_sections_data["cnvs"] = report_sections_data["cnvs"]

    if "CNV_PROFILE" in report_sections:
        report_sections_data["cnv_profile_base64"] = get_plot(
            os.path.basename(
                _sample_file_path(sample, primary_analysis_file_key("dna", "CNV_PROFILE"))
            ),
            assay_config,
        )

    if "BIOMARKER" in report_sections:
        report_sections_data["biomarkers"] = list(
            biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"])) or []
        )
        rule_sections_data["biomarkers"] = report_sections_data["biomarkers"]

    if "TRANSLOCATION" in report_sections:
        report_sections_data["translocs"] = list(
            translocation_repository.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
            or []
        )
        rule_sections_data["translocs"] = report_sections_data["translocs"]

    if "FUSION" in report_sections:
        report_sections_data["fusions"] = []
        rule_sections_data["fusions"] = report_sections_data["fusions"]

    assay_config["reporting"]["report_header"] = get_report_header(
        assay_group,
        sample,
        assay_config["reporting"].get("report_header", "Unknown"),
    )

    vep_variant_class_meta = vep_metadata_repository.get_variant_class_translations(
        sample_vep_version
    )
    selected_list_ids = list(
        dict.fromkeys(
            [
                *snv_filters.get("snvlists", []),
                *cnv_filters.get("cnvlists", []),
            ]
        )
    )
    selected_list_docs = gene_list_repository.get_isgl_by_ids(selected_list_ids)
    applied_gene_lists = [
        {
            **document,
            "isgl_id": isgl_id,
            "selected_for": [
                domain
                for domain, selected_ids in (
                    ("snv", snv_filters.get("snvlists", [])),
                    ("cnv", cnv_filters.get("cnvlists", [])),
                )
                if isgl_id in selected_ids
            ],
        }
        for isgl_id, document in selected_list_docs.items()
    ]
    prepared_rule_context = prepare_report_context(
        sample=sample,
        asp=assay_panel_doc or {},
        aspc=assay_config,
        analyte="dna",
        applied_gene_lists=applied_gene_lists,
        report_sections_data=rule_sections_data,
    )
    clinical_rule_evaluation = (
        clinical_rule_service.evaluate(
            aspc=assay_config,
            context=prepared_rule_context,
        )
        if clinical_rule_service is not None
        else None
    )
    germline_rule_evaluation = None
    if (
        "germline" in set(sample.get("analysis_intents") or [])
        and clinical_rule_service is not None
    ):
        germline_rule_context = prepare_report_context(
            sample=sample,
            asp=assay_panel_doc or {},
            aspc=assay_config,
            analyte="dna",
            applied_gene_lists=applied_gene_lists,
            report_sections_data={"snvs": germline_variants},
            intent="germline",
        )
        germline_rule_evaluation = clinical_rule_service.evaluate(
            aspc=assay_config,
            context=germline_rule_context,
        )

    report_date = datetime.now().date()
    report_timestamp: str = shared_get_report_timestamp()
    somatic_summary = rendered_summary(clinical_rule_evaluation)
    germline_summary = rendered_summary(germline_rule_evaluation)
    if "germline" in set(sample.get("analysis_intents") or []) and not germline_summary:
        germline_summary = (
            '<strong style="color:#b42318">Germline SNV report text has not been '
            "configured for this ASP and subpanel.</strong>"
        )
    template_context: Dict[str, Any] = {
        "assay_config": assay_config,
        "report_sections": report_sections,
        "report_sections_data": report_sections_data,
        "sample": sample,
        "translation": VARIANT_CLASS_TRANSLATION,
        "vep_var_class_translations": vep_variant_class_meta,
        "class_desc": TIER_DESC,
        "class_desc_short": TIER_SHORT_DESC,
        "report_date": report_date,
        "report_timestamp": report_timestamp,
        "save": save,
        "sample_assay": sample_assay,
        "assay_group": assay_group,
        "genes_covered_in_panel": genes_covered_in_panel,
        "panel_doc": json.dumps(assay_panel_doc, default=str),
        "report_snvlists": json.dumps(genes_covered_in_panel, default=str),
        "report_sample_filters": json.dumps(sample_filters, default=str),
        "clinical_summary_text": "\n\n".join(
            text for text in (somatic_summary, germline_summary) if text
        ),
        "clinical_germline_summary_text": germline_summary,
        "clinical_rule_evaluation": (
            clinical_rule_evaluation.model_dump(mode="json") if clinical_rule_evaluation else None
        ),
    }
    return "dna_report.html", template_context, snapshot_rows
