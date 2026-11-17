# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""DNA result tables and details for smd-reports."""

import math

from .formatting import (
    _annotation,
    _comment,
    _copy_number,
    _detail,
    _format_classification,
    _hgvs,
    _perc_no_dec,
    _read_support,
    _summary_copy_number,
)
from .sections import ReportSections


class DnaResultSections:
    """Render DNA SNVs, copy-number calls and translocations as separate analyses."""

    def __init__(self, document: ReportSections) -> None:
        """Bind the current document's resolved inputs and output sections."""
        self.document = document

    def append(self) -> None:
        """Append enabled DNA result tables and their existing detail cards."""
        self.append_small_variants()
        self.document.sections.append(
            {"key": "notation", "kind": "text", "text": "Note: p = protein, c = cDNA, g = genomic"}
        )
        self.append_copy_numbers()
        self.append_translocations()

    def append_small_variants(self) -> None:
        """Render somatic and optional germline SNV results."""
        data = self.document.data
        enabled = self.document.enabled
        sections = self.document.sections
        details = self.document.details
        add_table = self.document.add_table
        if "SNV" in enabled:
            for key, heading, empty_key in [
                ("snvs", "Kliniskt relevanta SNVs och små INDELs", "SNV"),
                (
                    "germline_snvs",
                    "Kliniskt relevanta germline-SNVs och små INDELs",
                    "GERMLINE_SNV",
                ),
            ]:
                if key == "germline_snvs" and data.get(key) is None:
                    continue
                rows = data.get(key) or []
                add_table(
                    key,
                    heading,
                    ["Gen", "Mutation", "Variantfrekvens", "Klassificering"],
                    [
                        [
                            row.get("symbol"),
                            row.get("cdna")
                            if (row.get("indel_size") or 0) > 20
                            else _hgvs(row.get("variant")),
                            _perc_no_dec(row.get("af")),
                            row.get("class_short_desc")
                            if row.get("class") in (1, 2, 3, 4)
                            else "-",
                        ]
                        for row in rows
                    ],
                    empty_key,
                )
                sections[-1]["cell_options"] = {
                    str(index): {"3": {"font_weight": "semibold"}}
                    for index, row in enumerate(rows)
                    if row.get("class") == 1
                }
                # Existing detailed cards belong to the somatic result section only.
                if key != "snvs":
                    continue
                for index, row in enumerate(rows):
                    protein = "\n".join(
                        str(value)
                        for value in (row.get("protein_changes") or [row.get("variant")])
                        if value is not None
                    )
                    feature = str(row.get("feature") or "")
                    if row.get("exon"):
                        feature += f", exon {row['exon'][0]}"
                    elif row.get("intron"):
                        feature += f", intron {row['intron'][0]}"
                    name = str(_hgvs(row.get("variant")) or "")
                    if len(name) >= 30:
                        name = row.get("cdna") or ""
                    details.append(
                        _detail(
                            f"snv-{index}",
                            f"{row.get('symbol', '')}: {name or row.get('cdna', '')}",
                            [
                                ("Gen", row.get("symbol")),
                                (
                                    "Typ",
                                    f"{row.get('class_type', '')} {row.get('variant_class', '')}",
                                ),
                                ("Transkript", feature),
                                ("Konsekvens", row.get("consequence")),
                                (
                                    "cDNA-förändring",
                                    _hgvs(row.get("cdna"))
                                    if row.get("var_type") == "snv"
                                    else row.get("cdna"),
                                ),
                                (
                                    "Proteinförändring",
                                    protein
                                    if (row.get("indel_size") or 0) < 20
                                    else row.get("cdna"),
                                ),
                                ("Kromosom", f"chr{row.get('chr', '')}"),
                                ("Position (hg38)", row.get("pos")),
                                ("Frekvens", _perc_no_dec(row.get("af"))),
                                ("Exon", "/".join(row.get("exon") or []) or "-"),
                                ("Intron", "/".join(row.get("intron") or []) or "-"),
                                (
                                    "Klassificering",
                                    _format_classification(
                                        row.get("class"), row.get("class_long_desc")
                                    ),
                                ),
                                ("Kommentar", _comment(row, selected=True)),
                            ],
                        )
                    )

    def append_copy_numbers(self) -> None:
        """Render CNV measurements without combining caller event text and numeric ratio."""
        data = self.document.data
        enabled = self.document.enabled
        short = self.document.short
        details = self.document.details
        add_table = self.document.add_table
        if "CNV" in enabled:
            cnvs = data.get("cnvs") or []
            rows = []
            for index, row in enumerate(cnvs):
                genes = row.get("genes") or []
                selected = [gene.get("gene", "") for gene in genes if gene.get("class")]
                other = len(genes) - len(selected)
                label = " ".join(selected) + (f" + {other} other genes" if other else "")
                tier = (row.get("classification") or {}).get("class")
                ratio = row.get("ratio")
                rows.append(
                    [
                        label.strip(),
                        f"{row.get('size', '-')} bp",
                        ("AMP" if ratio > 1 else "DUP" if ratio > 0 else "DEL")
                        if isinstance(ratio, (int, float))
                        and not isinstance(ratio, bool)
                        and math.isfinite(ratio)
                        else "-",
                        _summary_copy_number(ratio),
                    ]
                )
                details.append(
                    _detail(
                        f"cnv-{index}",
                        ", ".join(gene.get("gene", "") for gene in genes),
                        [
                            ("Kromosom", row.get("chr")),
                            ("Region", f"{row.get('start', '-')}-{row.get('end', '-')}"),
                            ("Storlek", f"{row.get('size', '-')} bp"),
                            ("Typ", row.get("type")),
                            ("Kopietal", _copy_number(row.get("ratio"))),
                            ("Prober", row.get("nprobes")),
                            ("Paired reads (PR)", row.get("PR")),
                            ("Split reads (SR)", row.get("SR")),
                            ("Klassificering", _format_classification(tier, short.get(tier))),
                            ("Kommentar", _comment(row)),
                        ],
                    )
                )
            add_table(
                "cnvs",
                "Kliniskt relevanta genspecifika kopietalsförändringar",
                ["Gen(er)", "Storlek", "Typ", "Kopietal"],
                rows,
                "CNV",
            )

    def append_translocations(self) -> None:
        """Render DNA translocations using the selected partner annotation."""
        data = self.document.data
        enabled = self.document.enabled
        short = self.document.short
        details = self.document.details
        add_table = self.document.add_table
        if "TRANSLOCATION" in enabled:
            rows = []
            for index, row in enumerate(data.get("translocs") or []):
                ann = _annotation(row)
                tier = (row.get("classification") or {}).get("class")
                title = (ann.get("Gene_Name") or "-").replace("&", "::")
                exon = ann.get("Rank") or ann.get("EXON") or "-"
                rows.append(
                    [
                        title,
                        _hgvs(ann.get("HGVSp")),
                    ]
                )
                fields = [
                    ("Position", f"{row.get('CHROM', '')}:{row.get('POS', '')}"),
                    ("Allele", row.get("ALT")),
                    ("Exon", exon),
                ]
                for genotype in row.get("GT") or []:
                    fields.extend(
                        [
                            ("Prov", genotype.get("type") or genotype.get("sample")),
                            ("Paired reads (PR)", _read_support(genotype.get("PR"))),
                            ("Split reads (SR)", _read_support(genotype.get("SR"))),
                        ]
                    )
                fields.extend(
                    [
                        ("Klassificering", _format_classification(tier, short.get(tier))),
                        ("Kommentar", _comment(row)),
                    ]
                )
                details.append(_detail(f"translocation-{index}", title, fields))
            add_table(
                "translocations",
                "Kliniskt relevanta fusioner",
                ["Gener", "HGVS.p"],
                rows,
                "TRANSLOCATION",
            )
