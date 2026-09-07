#!/usr/bin/env python3
"""Validate and publish the NCI TP53 functional/structural variant release."""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Sequence
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


def _first(row: dict[str, Any], names: Sequence[str]) -> str | None:
    for name in names:
        value = clean_text(row.get(name))
        if value is not None:
            return value
    return None


def documents(path: Path) -> Iterator[dict[str, Any]]:
    """Map MutationView R21-compatible fields to the TP53 lookup contract."""
    for line_number, row in delimited_rows(path):
        identifier = parse_int(row.get("MUT_ID"))
        hgvsc = _first(row, ("c_description", "c.Description", "cDNA_description"))
        if identifier is None or hgvsc is None:
            raise ValueError(f"Missing TP53 variant identity at {path}:{line_number}")
        yield without_missing(
            {
                "id": identifier,
                "var": hgvsc,
                "polymorphism": _first(row, ("Polymorphism",)),
                "cpg": _first(row, ("CpG_site", "CpG")),
                "splice": _first(row, ("Splice_site", "SpliceSite")),
                "transactivation_class": _first(
                    row, ("TransactivationClass", "Transactivation_class")
                ),
                "AGVGD_class": _first(row, ("AGVGDClass", "AGVGD_class")),
                "residue_func": _first(row, ("Residue_function", "ResidueFunction")),
                "motif": _first(row, ("Structural_motif", "StructuralMotif")),
                "structure_function_class": _first(
                    row, ("StructureFunctionClass", "Structure_Function_Class")
                ),
                "domain_func": _first(row, ("Domain_function", "DomainFunction")),
                "n_somatic": parse_int(row.get("Somatic_count")),
                "n_germline": parse_int(row.get("Germline_count")),
                "hgvsg_hg19": _first(row, ("g_description",)),
                "hgvsg_hg38": _first(row, ("g_description_GRCh38",)),
                "hgvsp": _first(row, ("ProtDescription",)),
                "effect": _first(row, ("Effect",)),
                "hotspot": _first(row, ("Hotspot",)),
                "external_cohort_count": parse_int(row.get("TCGA_ICGC_GENIE_count")),
                "source_record": source_fields(row),
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="MutationView release file, such as MutationView_r21.csv.",
    )
    add_common_arguments(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = CollectionSpec(
        name=mapped_collection(args, "iarc_tp53_collection"),
        documents=lambda: documents(args.input),
        indexes=(
            ((("id", 1),), {"name": "id_1", "unique": True}),
            ((("var", 1),), {"name": "var_1"}),
            ((("hgvsg_hg38", 1),), {"name": "hgvsg_hg38_1", "sparse": True}),
            ((("hgvsp", 1),), {"name": "hgvsp_1", "sparse": True}),
        ),
    )
    return finish_command(
        args,
        lambda: execute_update(
            args,
            source="nci_tp53",
            paths=[args.input],
            specs=[spec],
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
