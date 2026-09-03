#!/usr/bin/env python3
"""Validate and publish a BRCA Exchange full TSV release."""

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
    without_missing,
)


def _coordinate(value: Any) -> tuple[str, int, str, str] | None:
    text = clean_text(value)
    if text is None:
        return None
    parts = text.removeprefix("chr").split("-", 3)
    if len(parts) != 4:
        return None
    try:
        return parts[0], int(parts[1]), parts[2], parts[3]
    except ValueError:
        return None


def documents(path: Path) -> Iterator[dict[str, Any]]:
    """Map the current BRCA Exchange full export to the application contract."""
    for line_number, row in delimited_rows(path):
        identifier = clean_text(row.get("id"))
        chromosome = clean_text(row.get("Chr"))
        position = parse_int(row.get("Pos"))
        reference = clean_text(row.get("Ref"))
        alternate = clean_text(row.get("Alt"))
        if None in {identifier, chromosome, position, reference, alternate}:
            raise ValueError(f"Missing GRCh37 variant identity at {path}:{line_number}")
        hg38 = _coordinate(row.get("Genomic_Coordinate_hg38"))
        normalized = {
            "id": identifier,
            "chr": chromosome.removeprefix("chr"),
            "pos": position,
            "ref": reference,
            "alt": alternate,
            "enigma_clinsig": clean_text(row.get("Clinical_significance_ENIGMA")) or "",
            "enigma_clinsig_refs": clean_text(row.get("Clinical_significance_citations_ENIGMA"))
            or "",
            "enigma_clinsig_comment": clean_text(row.get("Comment_on_clinical_significance_ENIGMA"))
            or "",
            "gene": clean_text(row.get("Gene_Symbol")),
            "transcript": clean_text(row.get("Reference_Sequence")),
            "hgvsc": clean_text(row.get("HGVS_cDNA")),
            "hgvsp": clean_text(row.get("HGVS_Protein")),
            "pathogenicity_expert": clean_text(row.get("Pathogenicity_expert")),
            "pathogenicity_all": clean_text(row.get("Pathogenicity_all")),
            "source_url": clean_text(row.get("Source_URL")),
            "source_record": source_fields(row),
        }
        if hg38:
            normalized.update(
                {"chr38": hg38[0], "pos38": hg38[1], "ref38": hg38[2], "alt38": hg38[3]}
            )
        yield without_missing(normalized)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="BRCA Exchange full TSV file.")
    add_common_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = CollectionSpec(
        name=mapped_collection(args, "brcaexchange_collection"),
        documents=lambda: documents(args.input),
        indexes=(
            ((("id", 1),), {"name": "id_1", "unique": True}),
            (
                (("chr", 1), ("pos", 1), ("ref", 1), ("alt", 1)),
                {"name": "chr_pos_ref_alt"},
            ),
            (
                (("chr38", 1), ("pos38", 1), ("ref38", 1), ("alt38", 1)),
                {"name": "chr38_pos38_ref38_alt38", "sparse": True},
            ),
            ((("gene", 1),), {"name": "gene_1", "sparse": True}),
        ),
    )
    return finish_command(
        args,
        lambda: execute_update(
            args,
            source="brca_exchange",
            paths=[args.input],
            specs=[spec],
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
