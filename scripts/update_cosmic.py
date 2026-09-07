#!/usr/bin/env python3
"""Validate and publish selected licensed COSMIC product archives."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import tarfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
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
    archive_extension: str = ".tar"
    archive_has_assembly: bool = True


RECORD_KEY_INDEX = (("record_key", 1),)


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
            (
                (("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)),
                {"name": "genomic_variant"},
            ),
            ((("id", 1),), {"name": "cosmic_id_1"}),
            ((("gene", 1),), {"name": "gene_1", "sparse": True}),
        ),
    ),
    "targeted_variants": Product(
        "cosmic_targeted_collection",
        "Cosmic_CompleteTargetedScreensMutant_VcfNormal_",
        ".vcf.gz",
        "vcf",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)), {"name": "genomic_variant"}),
            ((("id", 1),), {"name": "cosmic_id_1"}),
            ((("gene", 1), ("hgvsp", 1)), {"name": "gene_hgvsp", "sparse": True}),
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
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
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
    "classification_papers": Product(
        "cosmic_classification_paper_collection",
        "Cosmic_ClassificationPaper_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("cosmic_phenotype_paper_id", 1),), {"name": "phenotype_paper_id_1"}),
            ((("cosmic_phenotype_id", 1),), {"name": "phenotype_id_1"}),
        ),
    ),
    "cancer_gene_census": Product(
        "cosmic_cgc_collection",
        "Cosmic_CancerGeneCensus_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("gene_symbol", 1),), {"name": "gene_1", "unique": True}),
            ((("cosmic_gene_id", 1),), {"name": "cosmic_gene_id_1"}),
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
    "genes": Product(
        "cosmic_genes_collection",
        "Cosmic_Genes_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("cosmic_gene_id", 1),), {"name": "cosmic_gene_id_1", "unique": True}),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
            ((("hgnc_id", 1),), {"name": "hgnc_id_1", "sparse": True}),
        ),
    ),
    "transcripts": Product(
        "cosmic_transcripts_collection",
        "Cosmic_Transcripts_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("transcript_accession", 1),), {"name": "transcript_1", "unique": True}),
            ((("cosmic_gene_id", 1),), {"name": "cosmic_gene_id_1"}),
        ),
    ),
    "census_gene_mutations": Product(
        "cosmic_mutant_census_collection",
        "Cosmic_MutantCensus_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("genomic_mutation_id", 1),), {"name": "mutation_id_1"}),
            (
                (
                    ("chromosome", 1),
                    ("genome_start", 1),
                    ("genomic_wt_allele", 1),
                    ("genomic_mut_allele", 1),
                ),
                {"name": "genomic_variant"},
            ),
            ((("gene_symbol", 1), ("hgvsp", 1)), {"name": "gene_hgvsp", "sparse": True}),
        ),
    ),
    "resistance_mutations": Product(
        "cosmic_resistance_collection",
        "Cosmic_ResistanceMutations_Tsv_",
        ".tsv.gz",
        "tsv",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("genomic_mutation_id", 1),), {"name": "mutation_id_1", "sparse": True}),
            ((("gene_symbol", 1),), {"name": "gene_1"}),
        ),
    ),
    "mutation_census": Product(
        "cosmic_mutation_census_collection",
        "CancerMutationCensus_AllData_Tsv_",
        ".tsv.gz",
        "mutation_census",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("genomic_mutation_id", 1),), {"name": "mutation_id_1"}),
            (
                (("chr_grch38", 1), ("start_grch38", 1), ("ref", 1), ("alt", 1)),
                {"name": "grch38_variant"},
            ),
            (
                (("chr_grch37", 1), ("start_grch37", 1), ("ref", 1), ("alt", 1)),
                {"name": "grch37_variant"},
            ),
            ((("gene_name", 1), ("mutation_aa", 1)), {"name": "gene_protein"}),
        ),
    ),
    "actionability": Product(
        "cosmic_actionability_collection",
        "Actionability_AllData_Tsv_",
        ".tsv",
        "tsv",
        (
            ((("record_key", 1),), {"name": "record_key_1", "unique": True}),
            ((("genes", 1),), {"name": "genes_1"}),
            ((("classification_id", 1),), {"name": "classification_id_1"}),
        ),
    ),
    "signature_sbs": Product(
        "cosmic_signature_sbs_collection",
        "COSMIC_catalogue-signatures_SBS96_",
        ".txt",
        "signature",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("signature", 1),), {"name": "signature_1", "unique": True}),
        ),
        archive_extension=".zip",
        archive_has_assembly=False,
    ),
    "signature_dbs": Product(
        "cosmic_signature_dbs_collection",
        "COSMIC_catalogue-signatures_DBS78_",
        ".txt",
        "signature",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("signature", 1),), {"name": "signature_1", "unique": True}),
        ),
        archive_extension=".zip",
        archive_has_assembly=False,
    ),
    "signature_sv": Product(
        "cosmic_signature_sv_collection",
        "COSMIC_catalogue-signatures_SV32_",
        ".txt",
        "signature",
        (
            (RECORD_KEY_INDEX, {"name": "record_key_1", "unique": True}),
            ((("signature", 1),), {"name": "signature_1", "unique": True}),
        ),
        archive_extension=".zip",
        archive_has_assembly=False,
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
    "aa_mut_start",
    "aa_mut_stop",
    "cosmic_sample_tested",
    "cosmic_sample_mutated",
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
    "exac_af",
    "exac_afr_af",
    "exac_amr_af",
    "exac_adj_af",
    "exac_eas_af",
    "exac_fin_af",
    "exac_nfe_af",
    "exac_sas_af",
    "gerp_rs",
    "min_sift_score",
}

_GENOMIC_LOCATION = re.compile(r"(?:chr)?([^:]+):(\d+)-(\d+)$", re.IGNORECASE)
_ACTIONABILITY_PREFIX_SYMBOL = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z0-9]{1,14})(?=[_-])")
_ACTIONABILITY_STANDALONE_SYMBOL = re.compile(r"(?<=[(,\- ])\??([A-Z][A-Z0-9]{1,14})(?=[, )])")
_ACTIONABILITY_NON_GENES = {"AND", "COSF", "ITD", "NOT", "OR"}


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


def _quality_value(value: str) -> float | str | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def vcf_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Stream complete normalized COSMIC VCF records without extracting the archive."""
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
            chromosome, position_text, cosmic_id, reference, alternates, quality, filters = columns[
                :7
            ]
            info = _info_fields(columns[7])
            position = int(position_text)
            for alternate in alternates.split(","):
                count_value = next(
                    (
                        info[key]
                        for key in (
                            "targeted_screen_sample_count",
                            "genome_screen_sample_count",
                            "sample_count",
                        )
                        if key in info
                    ),
                    None,
                )
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
                        "qual": _quality_value(quality),
                        "filter": clean_text(filters),
                        "info": info,
                        "format": clean_text(columns[8]) if len(columns) > 8 else None,
                        "samples": columns[9:] if len(columns) > 9 else None,
                        "cnt": counts,
                        "gene": info.get("gene"),
                        "transcript": info.get("transcript"),
                        "strand": info.get("strand"),
                        "legacy_id": info.get("legacy_id"),
                        "cds": info.get("cds"),
                        "aa": info.get("aa"),
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
        if field in FLOAT_FIELDS or (
            field.endswith("_af") and field.startswith(("exac_", "gnomad_"))
        ):
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


def _locus_fields(value: Any, assembly: str) -> dict[str, Any]:
    text = clean_text(value)
    match = _GENOMIC_LOCATION.fullmatch(text or "")
    if match is None:
        return {}
    chromosome, start, end = match.groups()
    suffix = assembly.lower()
    return {
        f"chr_{suffix}": chromosome.removeprefix("chr"),
        f"start_{suffix}": int(start),
        f"end_{suffix}": int(end),
    }


def mutation_census_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Preserve CMC rows and add indexed GRCh37/GRCh38 variant identities."""
    for document in tsv_documents(path, ".tsv.gz"):
        document.update(_locus_fields(document.get("mutation_genome_position_grch37"), "grch37"))
        document.update(_locus_fields(document.get("mutation_genome_position_grch38"), "grch38"))
        document["ref"] = document.get("genomic_wt_allele_seq")
        document["alt"] = document.get("genomic_mut_allele_seq")
        yield without_missing(document)


def actionability_documents(path: Path, suffix: str) -> Iterator[dict[str, Any]]:
    """Preserve Actionability rows and derive indexed gene symbols from its expression."""
    for document in tsv_documents(path, suffix):
        remark = str(document.get("mutation_remark") or "")
        candidates = [
            *_ACTIONABILITY_PREFIX_SYMBOL.findall(remark),
            *_ACTIONABILITY_STANDALONE_SYMBOL.findall(remark),
        ]
        genes = list(
            dict.fromkeys(
                symbol
                for symbol in candidates
                if symbol not in _ACTIONABILITY_NON_GENES
                and not symbol.startswith(("COSF", "COSV", "COSM"))
            )
        )
        if genes:
            document["genes"] = genes
        yield document


def signature_documents(
    path: Path, *, signature_class: str, assembly: str
) -> Iterator[dict[str, Any]]:
    """Transpose one COSMIC signature matrix into query-efficient signature documents."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Cannot read COSMIC signature archive {path}: {exc}") from exc
    members = [name for name in archive.namelist() if name.endswith(".txt")]
    if len(members) != 1:
        archive.close()
        raise ValueError(f"Expected one *.txt member in {path}, found {len(members)}")
    if assembly not in members[0]:
        archive.close()
        raise ValueError(
            f"Signature matrix {members[0]} does not match requested assembly {assembly}"
        )
    with archive, archive.open(members[0]) as raw:
        handle = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or reader.fieldnames[0] != "Type":
            raise ValueError(f"COSMIC signature matrix has no Type header: {path}")
        signatures = reader.fieldnames[1:]
        profiles: dict[str, dict[str, float]] = {name: {} for name in signatures}
        for row in reader:
            mutation_type = clean_text(row.get("Type"))
            if mutation_type is None:
                continue
            for signature in signatures:
                value = parse_float(row.get(signature))
                if value is not None:
                    profiles[signature][mutation_type] = value
        for source_row, signature in enumerate(signatures, start=1):
            yield {
                "record_key": record_key(signature_class, assembly, signature),
                "source_row": source_row,
                "signature": signature,
                "signature_class": signature_class,
                "assembly": assembly,
                "profile": profiles[signature],
            }


def _find_archive(directory: Path, product: Product, release: str, assembly: str) -> Path:
    matches = sorted(directory.glob(f"{product.archive_prefix}*{product.archive_extension}"))
    release_pattern = re.compile(rf"_v{re.escape(release)}(?:_|\.)")
    matches = [path for path in matches if release_pattern.search(path.name)]
    if assembly and product.archive_has_assembly:
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
        if product.file_type == "vcf":
            factory = partial(vcf_documents, path)
        elif product.file_type == "mutation_census":
            factory = partial(mutation_census_documents, path)
        elif product.file_type == "signature":
            signature_class = args.product.removeprefix("signature_").upper()
            factory = partial(
                signature_documents,
                path,
                signature_class=signature_class,
                assembly=args.assembly,
            )
        elif args.product == "actionability":
            factory = partial(actionability_documents, path, product.data_suffix)
        else:
            factory = partial(tsv_documents, path, product.data_suffix)
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
