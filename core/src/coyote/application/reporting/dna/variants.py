# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Transform already eligible DNA variants into report display values."""

from __future__ import annotations

from coyote.application.reporting.eligibility import (
    classification_is_usable,
)
from coyote.domain.common.reporting import (
    TIER_DESC,
    TIER_SHORT_DESC,
    VARIANT_CLASS_TRANSLATION,
)
from coyote.domain.dna.notation import one_letter_p, standard_hgvs


def hotspot_variant(variants: list) -> list[dict]:
    """
    Return variants with HOTSPOT keys hydrated from hotspot payloads.
    """
    hydrated_variants = []
    for variant in variants:
        hotspot_records = variant.get("hotspots") or []
        hotspot_dict = hotspot_records[0] if hotspot_records else {}
        if isinstance(hotspot_dict, dict):
            matched_hotspots = []
            for hotspot_key, hotspot_elements in hotspot_dict.items():
                elements = (
                    hotspot_elements
                    if isinstance(hotspot_elements, (list, tuple, set))
                    else [hotspot_elements]
                )
                if any("COS" in str(element) for element in elements if element is not None):
                    matched_hotspots.append(hotspot_key)
            if matched_hotspots:
                hydrated_hotspots = variant.setdefault("INFO", {}).setdefault("HOTSPOT", [])
                hydrated_hotspots.extend(
                    key for key in matched_hotspots if key not in hydrated_hotspots
                )
        hydrated_variants.append(variant)
    return hydrated_variants


def filter_variants_for_report(
    variants: list,
    filter_genes: list,
    allowed_tiers: list[int],
    *,
    restrict_to_genes: bool = False,
) -> list:
    """Select reportable SNVs and sort them by tier.

    Args:
        variants: Hydrated findings with scope-matched classifications.
        filter_genes: Selected report gene symbols.
        allowed_tiers: ASPC tier policy; an empty list excludes all findings.
        restrict_to_genes: Treat an empty selected gene list as an empty scope
            instead of an unrestricted report.

    Returns:
        Nonblacklisted findings within the gene and tier selection.
    """
    return sorted(
        [
            var
            for var in variants
            if (
                var.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL") in filter_genes
                or (not restrict_to_genes and len(filter_genes) == 0)
            )
            and not var.get("blacklist")
            and classification_is_usable(var.get("classification"))
            and var.get("classification", {}).get("class") in allowed_tiers
        ],
        key=lambda var: var.get("classification", {}).get("class", 0),
    )


def sort_by_class_and_af(data: list[dict]) -> list[dict]:
    """Order report rows by tier, then descending numeric allele fraction.

    Args:
        data: Simplified report rows. AF may be numeric, None, or the display
            label ``N/A`` used for FLT3 structural findings.

    Returns:
        A new list with unavailable AF values last within each tier. Equal
        values retain their input order; displayed values are not modified.
    """
    return sorted(
        data,
        key=lambda row: (
            row["class"],
            -row["af"] if isinstance(row.get("af"), (int, float)) else float("inf"),
        ),
    )


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
                "variant_class": var.get("variant_class", ""),
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
