#!/usr/bin/env python3
"""
Export SNV/indel variants for one sample using assay default filters.

This script intentionally does not update sample["filters"]. It computes the
effective filter state from the assay configuration in memory, runs the same
SNV query builder used by the DNA variant page, and writes CSV output.

Examples:
    python scripts/export_default_filtered_variants.py --sample 25MD17060p-2
    python scripts/export_default_filtered_variants.py --sample 25MD17060p-2 --output /tmp/sample.snvs.csv
    python scripts/export_default_filtered_variants.py --sample 25MD17060p-2 --output -
"""
from __future__ import annotations

import argparse
import csv
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

store = None
util = None
build_query = None


BASE_COLUMNS = [
    "sample",
    "variant_id",
    "gene",
    "hgvsc",
    "hgvsp",
    "exon",
    "intron",
    "variant_class",
    "indel_size",
    "consequence",
    "gnomad_frequency",
    "tier",
    "chrom",
    "pos",
    "ref",
    "alt",
    "chr_pos",
    "hotspot",
    "flags",
]


REQUIRED_FILTER_KEYS = [
    "max_freq",
    "min_freq",
    "max_control_freq",
    "min_depth",
    "min_alt_reads",
    "max_popfreq",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export sample SNV/indel variants using assay default filters."
    )
    parser.add_argument("--sample", required=True, help="Sample name/id, as used in Coyote.")
    parser.add_argument(
        "--output",
        "-o",
        help="Output CSV path. Defaults to <sample>.default.filtered.snvs.csv. Use '-' for stdout.",
    )
    parser.add_argument(
        "--development",
        action="store_true",
        help="Load DevelopmentConfig instead of ProductionConfig.",
    )
    return parser.parse_args()


def load_app(development: bool):
    global build_query, store, util

    from coyote import init_app
    from coyote.extensions import store as coyote_store
    from coyote.extensions import util as coyote_util

    app = init_app(development=development)

    from coyote.blueprints.dna.varqueries import build_query as coyote_build_query

    build_query = coyote_build_query
    store = coyote_store
    util = coyote_util
    return app


def compact(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(compact(item) for item in value if compact(item))
    if isinstance(value, dict):
        return " | ".join(f"{key}={compact(val)}" for key, val in value.items())
    return str(value)


def get_selected_csq(variant: dict) -> dict:
    return variant.get("INFO", {}).get("selected_CSQ", {}) or {}


def get_tier(variant: dict) -> str:
    classification = variant.get("classification") or {}
    tier = classification.get("class")
    return "" if tier is None else str(tier)


def get_flags(variant: dict) -> str:
    flags = []
    if variant.get("fp"):
        flags.append("False positive")
    if variant.get("blacklist") and not variant.get("override_blacklist"):
        flags.append("Blacklisted")
    if variant.get("interesting"):
        flags.append("Interesting")
    if variant.get("irrelevant"):
        flags.append("Irrelevant")
    return " | ".join(flags)


def format_gt(gt: dict) -> str:
    parts = []
    for key in ["AF", "DP", "VD", "AD", "GT", "GQ"]:
        if key in gt and gt.get(key) is not None:
            parts.append(f"{key}={gt.get(key)}")
    return "; ".join(parts)


def gt_columns(variants: list[dict]) -> list[str]:
    columns = []
    seen = set()
    for variant in variants:
        for gt in sorted(variant.get("GT", []), key=lambda item: item.get("type", "")):
            label = f"{gt.get('type', 'sample')} ({gt.get('sample', '')})"
            if label not in seen:
                seen.add(label)
                columns.append(label)
    return columns


def row_for_variant(sample_name: str, variant: dict, genotype_columns: list[str]) -> dict:
    csq = get_selected_csq(variant)
    ref = compact(variant.get("REF"))
    alt = compact(variant.get("ALT"))
    indel_size = ""
    if ref or alt:
        indel_size = str(len(alt) - len(ref))

    row = {
        "sample": sample_name,
        "variant_id": compact(variant.get("_id")),
        "gene": compact(csq.get("SYMBOL")),
        "hgvsc": compact(csq.get("HGVSc")),
        "hgvsp": compact(csq.get("HGVSp")),
        "exon": compact(csq.get("EXON")),
        "intron": compact(csq.get("INTRON")),
        "variant_class": compact(variant.get("variant_class")),
        "indel_size": indel_size,
        "consequence": compact(csq.get("Consequence")),
        "gnomad_frequency": compact(variant.get("gnomad_frequency")),
        "tier": get_tier(variant),
        "chrom": compact(variant.get("CHROM")),
        "pos": compact(variant.get("POS")),
        "ref": ref,
        "alt": alt,
        "chr_pos": f"{compact(variant.get('CHROM'))}:{compact(variant.get('POS'))}",
        "hotspot": compact(variant.get("INFO", {}).get("HOTSPOT")),
        "flags": get_flags(variant),
    }

    gt_by_label = {
        f"{gt.get('type', 'sample')} ({gt.get('sample', '')})": format_gt(gt)
        for gt in variant.get("GT", [])
    }
    for column in genotype_columns:
        row[column] = gt_by_label.get(column, "")

    return row


def load_assay_config(sample: dict) -> dict:
    assay = sample.get("assay")
    profile = sample.get("profile", "production")
    assay_config = store.aspc_handler.get_aspc_no_meta(assay, profile)
    if not assay_config:
        raise RuntimeError(f"No assay config found for assay '{assay}' ({profile})")

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    return util.common.format_assay_config(deepcopy(assay_config), schema)


def build_default_filter_context(sample: dict, assay_config: dict) -> tuple[dict, dict, list[str]]:
    sample_assay = sample.get("assay")
    subpanel = sample.get("subpanel")
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)
    if not assay_panel_doc:
        raise RuntimeError(f"No assay panel found for assay '{sample_assay}'")

    default_filters = deepcopy(assay_config.get("filters", {}))
    default_filters.setdefault("genelists", [])

    if assay_config.get("use_diagnosis_genelist", False) and subpanel:
        diagnosis_genelist_ids = store.isgl_handler.get_isgl_ids(
            sample_assay, subpanel, "genelist", is_active=True
        )
        default_filters["genelists"] = list(
            dict.fromkeys([*default_filters.get("genelists", []), *diagnosis_genelist_ids])
        )

    missing = [key for key in REQUIRED_FILTER_KEYS if key not in default_filters]
    if missing:
        raise RuntimeError(
            f"Assay config for '{sample_assay}' is missing required filter keys: {', '.join(missing)}"
        )

    sample_for_filtering = deepcopy(sample)
    sample_for_filtering["filters"] = default_filters

    checked_genelist_docs = store.isgl_handler.get_isgl_by_ids(default_filters.get("genelists", []))
    _, filter_genes = util.common.get_sample_effective_genes(
        sample_for_filtering, assay_panel_doc, checked_genelist_docs
    )

    return sample_for_filtering, default_filters, filter_genes


def variants_for_sample_default_filters(sample_name: str) -> tuple[dict, dict, list[dict]]:
    sample = store.sample_handler.get_sample(sample_name)
    if not sample:
        raise RuntimeError(f"Sample '{sample_name}' not found")

    assay_config = load_assay_config(sample)
    sample_for_filtering, filters, filter_genes = build_default_filter_context(sample, assay_config)
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")

    filter_conseq = util.dna.get_filter_conseq_terms(filters.get("vep_consequences", []))
    disp_pos = []
    for verification_key, positions in assay_config.get("verification_samples", {}).items():
        if verification_key in sample.get("name", ""):
            disp_pos = positions
            break

    query = build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": filters["max_freq"],
            "min_freq": filters["min_freq"],
            "max_control_freq": filters["max_control_freq"],
            "min_depth": filters["min_depth"],
            "min_alt_reads": filters["min_alt_reads"],
            "max_popfreq": filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
        },
    )

    variants = list(store.variant_handler.get_case_variants(query))
    variants = store.blacklist_handler.add_blacklist_data(variants, assay_group)
    variants, _tiered_variants = util.dna.add_global_annotations(variants, assay_group, subpanel)
    variants = util.dna.hotspot_variant(variants)
    return sample_for_filtering, assay_config, variants


def write_csv(sample_name: str, variants: list[dict], output: str | None) -> Path | None:
    genotype_columns = gt_columns(variants)
    columns = [*BASE_COLUMNS, *genotype_columns]
    rows = [row_for_variant(sample_name, variant, genotype_columns) for variant in variants]

    if output == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return None

    path = Path(output or f"{sample_name}.default.filtered.snvs.csv")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> int:
    args = parse_args()
    app = load_app(development=args.development)
    with app.app_context():
        sample, _assay_config, variants = variants_for_sample_default_filters(args.sample)
        output_path = write_csv(sample.get("name", args.sample), variants, args.output)

    if output_path is not None:
        print(f"Wrote {len(variants)} variants to {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
