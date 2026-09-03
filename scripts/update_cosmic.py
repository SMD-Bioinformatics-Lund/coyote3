#!/usr/bin/env python3
"""Validate and publish selected licensed COSMIC product archives."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import tarfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from scripts.knowledgebase_update_common import (
    CollectionSpec,
    add_common_arguments,
    clean_text,
    execute_update,
    finish_command,
    mapped_collection,
    parse_float,
    parse_int,
    record_key,
    snake_case,
    without_missing,
)


@dataclass(frozen=True)
class Product:
    collection_key: str
    archive_prefix: str
    data_suffix: str
    file_type: str
    indexes: tuple[tuple[tuple[tuple[str, int], ...], dict[str, Any]], ...]


PRODUCTS: dict[str, Product] = {
    "coding_variants": Product(
        "cosmic_collection",
        "Cosmic_GenomeScreensMutant_VcfNormal_",
        ".vcf.gz",
        "vcf",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)), {"name": "genomic_variant"}),
            ((("id", 1),), {"name": "cosmic_id_1"}),
            ((("gene", 1), ("hgvsp", 1)), {"name": "gene_hgvsp", "sparse": True}),
        ),
    ),
    "noncoding_variants": Product(
        "cosmic_noncoding_collection",
        "Cosmic_NonCodingVariants_VcfNormal_",
        ".vcf.gz",
        "vcf",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)), {"name": "genomic_variant"}),
            ((("id", 1),), {"name": "cosmic_id_1"}),
            ((("gene", 1),), {"name": "gene_1", "sparse": True}),
        ),
    ),
    "breakpoints": Product(
        "cosmic_breakpoints_collection",
        "Cosmic_Breakpoints_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("cosmic_structural_id", 1),), {"name": "structural_id_1", "sparse": True}),
            ((("chrom_from", 1), ("location_from_min", 1)), {"name": "from_locus"}),
            ((("chrom_to", 1), ("location_to_min", 1)), {"name": "to_locus"}),
        ),
    ),
    "structural_variants": Product(
        "cosmic_structural_collection",
        "Cosmic_StructuralVariants_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("cosmic_structural_id", 1),), {"name": "structural_id_1"}),
            ((("chromosome_from", 1), ("location_from_min", 1)), {"name": "from_locus"}),
            ((("chromosome_to", 1), ("location_to_min", 1)), {"name": "to_locus"}),
        ),
    ),
    "copy_number": Product(
        "cosmic_cna_collection",
        "Cosmic_CompleteCNA_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("cosmic_cnv_id", 1),), {"name": "cnv_id_1"}),
            (
                (("chromosome", 1), ("genome_start", 1), ("genome_stop", 1)),
                {"name": "genomic_interval"},
            ),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
        ),
    ),
    "fusions": Product(
        "cosmic_fusion_collection",
        "Cosmic_Fusion_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("cosmic_fusion_id", 1),), {"name": "fusion_id_1", "sparse": True}),
            (
                (("five_prime_gene_symbol", 1), ("three_prime_gene_symbol", 1)),
                {"name": "fusion_partners"},
            ),
        ),
    ),
    "gene_expression": Product(
        "cosmic_expression_collection",
        "Cosmic_CompleteGeneExpression_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
            ((("cosmic_sample_id", 1),), {"name": "sample_1"}),
        ),
    ),
    "methylation": Product(
        "cosmic_methylation_collection",
        "Cosmic_CompleteDifferentialMethylation_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("chromosome", 1), ("position", 1)), {"name": "genomic_position"}),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
        ),
    ),
    "classifications": Product(
        "cosmic_classification_collection",
        "Cosmic_Classification_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("cosmic_phenotype_id", 1),), {"name": "phenotype_id_1", "unique": True}),
        ),
    ),
    "cgc_hallmarks": Product(
        "cosmic_cgc_hallmarks_collection",
        "Cosmic_CancerGeneCensusHallmarksOfCancer_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
        ),
    ),
    "actionability": Product(
        "cosmic_actionability_collection",
        "Actionability_AllData_Tsv_",
        ".tsv",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("genomic_mutation_id", 1),), {"name": "mutation_id_1", "sparse": True}),
            ((("fusion_id", 1),), {"name": "fusion_id_1", "sparse": True}),
            ((("classification_id", 1),), {"name": "classification_id_1"}),
        ),
    ),
}

INTEGER_FIELDS = {
    "position",
    "genome_start",
    "genome_stop",
    "location_from_min",
    "location_from_max",
    "location_to_min",
    "location_to_max",
    "total_cn",
    "minor_allele",
    "pubmed_pmid",
    "number_of_patients",
    "treated_number",
    "control_number",
}
FLOAT_FIELDS = {
    "z_score",
    "avg_beta_value_normal",
    "beta_value",
    "two_sided_p_value",
    "orr_treat",
    "orr_con",
    "dor_treat",
    "dor_con",
    "pfs_treat",
    "pfs_con",
    "ttp_treat",
    "ttp_con",
    "dcr_treat",
    "dcr_con",
    "os_treat",
    "os_con",
}


def _archive_data_stream(path: Path, suffix: str):
    try:
        archive = tarfile.open(path, mode="r:*")
    except tarfile.TarError as exc:
        raise ValueError(f"Cannot read COSMIC archive {path}: {exc}") from exc
    members = [member for member in archive.getmembers() if member.name.endswith(suffix)]
    if len(members) != 1:
        archive.close()
        raise ValueError(f"Expected one *{suffix} member in {path}, found {len(members)}")
    raw = archive.extractfile(members[0])
    if raw is None:
        archive.close()
        raise ValueError(f"Cannot read {members[0].name} from {path}")
    binary = gzip.GzipFile(fileobj=raw) if members[0].name.endswith(".gz") else raw
    text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
    return archive, text


def _info_fields(value: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in value.split(";"):
        if not item:
            continue
        key, separator, raw_value = item.partition("=")
        if not separator:
            result[snake_case(key)] = True
            continue
        decoded = unquote(raw_value)
        values = decoded.split(",")
        result[snake_case(key)] = values if len(values) > 1 else decoded
    return result


def vcf_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Stream normalized COSMIC VCF records without extracting the archive."""
    archive, handle = _archive_data_stream(path, ".vcf.gz")
    try:
        source_row = 0
        for line in handle:
            if line.startswith("#"):
                continue
            source_row += 1
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 8:
                raise ValueError(f"Malformed VCF row {source_row} in {path}")
            chromosome, position_text, cosmic_id, reference, alternates = columns[:5]
            info = _info_fields(columns[7])
            position = int(position_text)
            for alternate in alternates.split(","):
                count_value = info.get("genome_screen_sample_count", info.get("sample_count"))
                count = parse_int(count_value)
                counts = {}
                if count is not None:
                    counts["samples"] = count
                yield without_missing(
                    {
                        "record_key": record_key(
                            chromosome, position, cosmic_id, reference, alternate, info
                        ),
                        "source_row": source_row,
                        "id": cosmic_id,
                        "chr": chromosome.removeprefix("chr"),
                        "start": position,
                        "end": position + len(reference) - 1,
                        "ref": reference,
                        "alt": alternate,
                        "cnt": counts,
                        "gene": info.get("gene"),
                        "transcript": info.get("transcript"),
                        "legacy_id": info.get("legacy_id"),
                        "hgvsc": info.get("hgvsc"),
                        "hgvsp": info.get("hgvsp"),
                        "hgvsg": info.get("hgvsg"),
                        "is_canonical": info.get("is_canonical"),
                        "tier": info.get("tier"),
                        "so_term": info.get("so_term"),
                        "old_variant": info.get("old_variant"),
                    }
                )
    finally:
        handle.close()
        archive.close()


def _typed_tsv_value(field: str, value: Any) -> Any:
    try:
        if field in INTEGER_FIELDS:
            return parse_int(value)
        if field in FLOAT_FIELDS:
            return parse_float(value)
    except ValueError:
        # COSMIC occasionally uses accession-qualified positions in coordinate columns.
        return clean_text(value)
    return clean_text(value)


def tsv_documents(path: Path, suffix: str) -> Iterator[dict[str, Any]]:
    """Stream one COSMIC TSV product as typed, source-faithful flat records."""
    archive, handle = _archive_data_stream(path, suffix)
    try:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError(f"COSMIC product has no header: {path}")
        for source_row, row in enumerate(reader, start=1):
            normalized = {
                snake_case(str(key)): _typed_tsv_value(snake_case(str(key)), value)
                for key, value in row.items()
                if key is not None
            }
            normalized = without_missing(normalized)
            yield {
                "record_key": record_key(source_row, normalized),
                "source_row": source_row,
                **normalized,
            }
    finally:
        handle.close()
        archive.close()


def _find_archive(directory: Path, product: Product, release: str, assembly: str) -> Path:
    matches = sorted(directory.glob(f"{product.archive_prefix}*.tar"))
    expected_release = f"_v{release}_"
    matches = [path for path in matches if expected_release in path.name]
    if assembly:
        matches = [path for path in matches if f"_{assembly}.tar" in path.name]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {product.archive_prefix} archive for release {release} "
            f"and {assembly}, found {len(matches)}"
        )
    return matches[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--assembly", required=True, choices=("GRCh37", "GRCh38"))
    parser.add_argument(
        "--product",
        required=True,
        choices=tuple(PRODUCTS),
        help="One COSMIC product to replace in this run.",
    )
    add_common_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    def run() -> dict[str, Any]:
        product = PRODUCTS[args.product]
        path = _find_archive(args.directory, product, args.release, args.assembly)
        factory = (
            (lambda: vcf_documents(path))
            if product.file_type == "vcf"
            else (lambda: tsv_documents(path, product.data_suffix))
        )
        spec = CollectionSpec(
            name=mapped_collection(args, product.collection_key),
            documents=factory,
            indexes=product.indexes,
        )
        return execute_update(
            args,
            source=f"cosmic_{args.product}",
            paths=[path],
            specs=[spec],
            extra_metadata={"assembly": args.assembly, "product": args.product},
        )

    return finish_command(args, run)


if __name__ == "__main__":
    raise SystemExit(main())
