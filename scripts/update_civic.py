#!/usr/bin/env python3
"""Validate and publish CIViC feature and variant summary releases."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from scripts.knowledgebase_update_common import (
    CollectionSpec,
    add_common_arguments,
    clean_text,
    delimited_rows,
    execute_update,
    finish_command,
    mapped_collection,
    parse_int,
    source_fields,
    split_values,
    without_missing,
)


def _boolean(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def gene_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Map CIViC Gene features into the gene lookup collection."""
    for line_number, row in delimited_rows(path):
        if clean_text(row.get("feature_type")) != "Gene":
            continue
        gene_id = parse_int(row.get("feature_id"))
        name = clean_text(row.get("name"))
        url = clean_text(row.get("feature_civic_url"))
        reviewed = clean_text(row.get("last_review_date"))
        if gene_id is None or name is None or url is None or reviewed is None:
            raise ValueError(f"Incomplete CIViC Gene feature at {path}:{line_number}")
        yield without_missing(
            {
                "gene_id": gene_id,
                "entrez_id": parse_int(row.get("entrez_id")),
                "name": name,
                "description": clean_text(row.get("description")),
                "gene_civic_url": url,
                "last_review_date": reviewed,
                "feature_type": "Gene",
                "aliases": split_values(row.get("feature_aliases")),
                "ncit_id": clean_text(row.get("ncit_id")),
                "source_record": source_fields(row),
            }
        )


def variant_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Map current CIViC variant summaries, including fusion features."""
    for line_number, row in delimited_rows(path):
        variant_id = parse_int(row.get("variant_id"))
        variant = clean_text(row.get("variant"))
        url = clean_text(row.get("variant_civic_url"))
        reviewed = clean_text(row.get("last_review_date"))
        if variant_id is None or variant is None or url is None or reviewed is None:
            raise ValueError(f"Incomplete CIViC variant at {path}:{line_number}")
        yield without_missing(
            {
                "variant_id": variant_id,
                "variant_civic_url": url,
                "feature_type": clean_text(row.get("feature_type")),
                "feature_id": parse_int(row.get("feature_id")),
                "feature_name": clean_text(row.get("feature_name")),
                "feature_civic_url": clean_text(row.get("feature_civic_url")),
                "variant": variant,
                "variant_aliases": split_values(row.get("variant_aliases")),
                "is_flagged": _boolean(row.get("is_flagged")),
                "variant_groups": split_values(row.get("variant_groups")),
                "variant_types": split_values(row.get("variant_types")),
                "molecular_profile_id": parse_int(row.get("single_variant_molecular_profile_id")),
                "last_review_date": reviewed,
                "gene": clean_text(row.get("gene")),
                "entrez_id": parse_int(row.get("entrez_id")),
                "chromosome": clean_text(row.get("chromosome")),
                "start": parse_int(row.get("start")),
                "stop": parse_int(row.get("stop")),
                "reference_bases": clean_text(row.get("reference_bases")),
                "variant_bases": clean_text(row.get("variant_bases")),
                "representative_transcript": clean_text(row.get("representative_transcript")),
                "ensembl_version": parse_int(row.get("ensembl_version")),
                "reference_build": clean_text(row.get("reference_build")),
                "hgvs_expressions": split_values(row.get("hgvs_descriptions")),
                "allele_registry_id": clean_text(row.get("allele_registry_id")),
                "clinvar_ids": split_values(row.get("clinvar_ids")),
                "ncit_id": clean_text(row.get("ncit_id")),
                "five_prime_partner": clean_text(row.get("5_prime_partner")),
                "three_prime_partner": clean_text(row.get("3_prime_partner")),
                "vicc_compliant_name": clean_text(row.get("vicc_compliant_name")),
                "iscn_name": clean_text(row.get("iscn_name")),
                "source_record": source_fields(row),
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--variants", required=True, type=Path)
    add_common_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    specs = [
        CollectionSpec(
            name=mapped_collection(args, "civic_gene_collection"),
            documents=lambda: gene_documents(args.features),
            indexes=(
                ((("gene_id", 1),), {"name": "gene_id_1", "unique": True}),
                ((("name", 1),), {"name": "name_1"}),
                ((("entrez_id", 1),), {"name": "entrez_id_1", "sparse": True}),
            ),
        ),
        CollectionSpec(
            name=mapped_collection(args, "civic_variants_collection"),
            documents=lambda: variant_documents(args.variants),
            indexes=(
                ((("variant_id", 1),), {"name": "variant_id_1", "unique": True}),
                (
                    (("chromosome", 1), ("start", 1), ("reference_bases", 1), ("variant_bases", 1)),
                    {"name": "genomic_variant", "sparse": True},
                ),
                (
                    (("gene", 1), ("hgvs_expressions", 1)),
                    {"name": "gene_hgvs_expressions"},
                ),
                ((("gene", 1), ("variant", 1)), {"name": "gene_variant"}),
                (
                    (("five_prime_partner", 1), ("three_prime_partner", 1)),
                    {"name": "fusion_partners", "sparse": True},
                ),
            ),
        ),
    ]
    return finish_command(
        args,
        lambda: execute_update(
            args,
            source="civic",
            paths=[args.features, args.variants],
            specs=specs,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
