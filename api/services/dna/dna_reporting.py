#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""Shared DNA reporting/variant transformation helpers."""

from datetime import datetime
from copy import deepcopy
import os
from pprint import pformat
from typing import Any, Dict, List, Optional, Tuple
from flask import current_app as app
from flask import render_template
from coyote.extensions import store
from coyote.util.common_utility import CommonUtility
from coyote.util.report.report_util import ReportUtility
from api.services.reporting.report_paths import get_report_timestamp as shared_get_report_timestamp
from api.services.dna.query_builders import build_query
from api.services.interpretation.annotation_enrichment import (
    add_global_annotations as shared_add_global_annotations,
)
from api.services.dna.dna_filters import (
    get_filter_conseq_terms as shared_get_filter_conseq_terms,
)


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
    translation = ReportUtility.VARIANT_CLASS_TRANSLATION
    class_short_desc_list = ReportUtility.TIER_SHORT_DESC
    class_long_desc_list = ReportUtility.TIER_DESC
    one_letter_p = app.jinja_env.filters["one_letter_p"]
    standard_HGVS = app.jinja_env.filters["standard_HGVS"]

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
            variant = cdna = f"{var.get('INFO', {}).get('SVLEN')}bp {translation.get(sv_type, sv_type)}"
        else:
            variant = "?"

        if selected_csq.get("HGVSp", None):
            if -20 <= indel_size <= 20:
                var_type = "snv"
                variant = standard_HGVS(one_letter_p(selected_csq.get("HGVSp")))
                protein_changes = [
                    standard_HGVS(one_letter_p(selected_csq.get("HGVSp"))),
                    standard_HGVS(selected_csq.get("HGVSp")),
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
        exons = [e for e in (exon_raw.split("/") if isinstance(exon_raw, str) else []) if e and e.strip()]
        intron_raw = selected_csq.get("INTRON") or ""
        introns = [
            i for i in (intron_raw.split("/") if isinstance(intron_raw, str) else []) if i and i.strip()
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


def build_dna_report_payload(
    sample: dict,
    assay_config: dict,
    save: int = 0,
    include_snapshot: bool = False,
) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    """
    Build report HTML and optional reported-variant snapshot rows for DNA.
    """
    sample_assay = sample.get("assay")
    assay_group: str = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    report_sections = assay_config.get("reporting", {}).get("report_sections", [])
    report_sections_data: Dict[str, Any] = {}

    app.logger.debug(f"Assay group: {assay_group} - DNA config: {pformat(report_sections)}")
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(sample_assay, is_active=True)
    all_panel_genelist_names = CommonUtility.get_assay_genelist_names(insilico_panel_genelists)

    if not sample.get("filters"):
        sample = CommonUtility.merge_sample_settings_with_assay_config(sample, assay_config)

    sample_filters = deepcopy(sample.get("filters", {}))

    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict: list[dict] = store.isgl_handler.get_isgl_by_ids(checked_genelists)
    genes_covered_in_panel, filter_genes = CommonUtility.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )

    filter_conseq = shared_get_filter_conseq_terms(sample_filters.get("vep_consequences", []))

    disp_pos = []
    if assay_config.get("verification_samples"):
        if sample["name"] in assay_config["verification_samples"]:
            disp_pos = assay_config["verification_samples"][sample["name"]]

    query = build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": sample_filters["max_freq"],
            "min_freq": sample_filters["min_freq"],
            "max_control_freq": sample_filters["max_control_freq"],
            "min_depth": sample_filters["min_depth"],
            "min_alt_reads": sample_filters["min_alt_reads"],
            "max_popfreq": sample_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
            "fp": {"$ne": True},
            "irrelevant": {"$ne": True},
        },
    )

    variants = list(store.variant_handler.get_case_variants(query))
    variants = store.blacklist_handler.add_blacklist_data(variants, assay=assay_group)

    variants, tiered_variants = shared_add_global_annotations(variants, assay_group, subpanel)
    variants = hotspot_variant(variants)
    variants = filter_variants_for_report(variants, filter_genes, assay_group)

    latest_sample_comment = store.sample_handler.get_latest_sample_comment(sample_id=str(sample["_id"]))

    snapshot_rows: Optional[List[Dict[str, Any]]] = None
    if include_snapshot:
        snapshot_rows = []
        now_utc = datetime.utcnow()

        for v in variants:
            annotations_interesting = v.get("annotations_interesting", {})
            annotations_interesting_assay_specific = (
                annotations_interesting.get(assay_group)
                or annotations_interesting.get(f"{assay_group}:{subpanel}")
                or {}
            )
            sel = (v.get("INFO", {}) or {}).get("selected_CSQ", {}) or {}
            snapshot_rows.append(
                {
                    "var_oid": v.get("_id"),
                    "annotation_oid": v.get("classification", {}).get("_id", None),
                    "annotation_text_oid": annotations_interesting_assay_specific.get("_id", None),
                    "sample_comment_oid": (
                        latest_sample_comment.get("_id") if latest_sample_comment else None
                    ),
                    "var_type": v.get("variant_class"),
                    "simple_id": v.get("simple_id"),
                    "simple_id_hash": v.get("simple_id_hash"),
                    "tier": v.get("classification", {}).get("class"),
                    "gene": sel.get("SYMBOL") or (v.get("gene") or None),
                    "transcript": sel.get("Feature") or v.get("selected_csq_feature"),
                    "hgvsp": sel.get("HGVSp") or v.get("hgvsp"),
                    "hgvsc": sel.get("HGVSc") or v.get("hgvsc"),
                    "variant": v.get("classification", {}).get("variant"),
                    "created_on": now_utc,
                }
            )

    variants_simple = get_simple_variants_for_report(variants, assay_config)
    report_sections_data["snvs"] = sort_by_class_and_af(variants_simple)

    if "CNV" in report_sections:
        report_sections_data["cnvs"] = list(
            store.cnv_handler.get_interesting_sample_cnvs(sample_id=str(sample["_id"]))
        )

    if "CNV_PROFILE" in report_sections:
        report_sections_data["cnv_profile_base64"] = CommonUtility.get_plot(
            os.path.basename(sample.get("cnvprofile", "")), assay_config
        )

    if "BIOMARKER" in report_sections:
        report_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )

    if "TRANSLOCATION" in report_sections:
        report_sections_data["translocs"] = store.transloc_handler.get_interesting_sample_translocations(
            sample_id=str(sample["_id"])
        )

    if "FUSION" in report_sections:
        report_sections_data["fusions"] = []

    assay_config["reporting"]["report_header"] = CommonUtility.get_report_header(
        assay_group,
        sample,
        assay_config["reporting"].get("report_header", "Unknown"),
    )

    vep_variant_class_meta = store.vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))

    report_date = datetime.now().date()
    report_timestamp: str = shared_get_report_timestamp()
    fernet = app.config["FERNET"]

    html = render_template(
        "dna_report.html",
        assay_config=assay_config,
        report_sections=report_sections,
        report_sections_data=report_sections_data,
        sample=sample,
        translation=ReportUtility.VARIANT_CLASS_TRANSLATION,
        vep_var_class_translations=vep_variant_class_meta,
        class_desc=ReportUtility.TIER_DESC,
        class_desc_short=ReportUtility.TIER_SHORT_DESC,
        report_date=report_date,
        report_timestamp=report_timestamp,
        save=save,
        sample_assay=sample_assay,
        assay_group=assay_group,
        genes_covered_in_panel=genes_covered_in_panel,
        encrypted_panel_doc=CommonUtility.encrypt_json(assay_panel_doc, fernet),
        encrypted_genelists=CommonUtility.encrypt_json(genes_covered_in_panel, fernet),
        encrypted_sample_filters=CommonUtility.encrypt_json(sample_filters, fernet),
    )

    return html, snapshot_rows
