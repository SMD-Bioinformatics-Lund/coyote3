# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Pharmacogenomic result presentation."""

from .sections import ReportSections


class PharmacogenomicSections:
    """Present selected pharmacogenomic findings in either analyte."""

    def __init__(self, document: ReportSections) -> None:
        """Bind the current document's resolved inputs and output sections."""
        self.document = document

    def append(self) -> None:
        """Append enabled PGx results with their configured empty message."""
        context = self.document.context
        analyte = self.document.analyte
        data = self.document.data
        enabled = self.document.enabled
        add_table = self.document.add_table
        if "PGX" in enabled:
            pgx = (data.get("pgx") if analyte == "dna" else context.get("pgx")) or []
            add_table(
                "pgx",
                "Farmakogenomiska resultat",
                ["Gen", "Resultat"],
                [
                    [
                        row.get("gene") or row.get("symbol") or row.get("hugo_symbol"),
                        next(
                            (
                                row[key]
                                for key in ("result", "phenotype", "diplotype", "records")
                                if row.get(key) is not None and row[key] != ""
                            ),
                            None,
                        ),
                    ]
                    for row in pgx
                ],
                "PGX",
            )
