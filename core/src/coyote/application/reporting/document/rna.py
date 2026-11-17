# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""RNA fusion result tables and detail cards."""

from coyote.domain.common.reporting import TIER_DESC

from .formatting import _comment, _detail, _format_classification
from .sections import ReportSections


class RnaResultSections:
    """Render RNA fusion calls independently of DNA translocations."""

    def __init__(self, document: ReportSections) -> None:
        """Bind the current document's resolved inputs and output sections."""
        self.document = document

    def append(self) -> None:
        """Append RNA fusion results and their selected call evidence."""
        context = self.document.context
        sample = self.document.sample
        short = self.document.short
        details = self.document.details
        add_table = self.document.add_table
        rows = []
        for index, row in enumerate(
            sorted(
                context.get("fusions") or [],
                key=lambda item: (item.get("classification") or {}).get("class", 999),
            )
        ):
            calls = row.get("report_selected_calls") or []
            if not calls:
                raise ValueError("Report fusion requires its selected call")
            call = calls[0]
            tier = (row.get("classification") or {}).get("class")
            title = f"{row.get('gene1', '')}::{row.get('gene2', '')}"
            locus = f"{call.get('breakpoint1', '-')} | {call.get('breakpoint2', '-')}"
            rows.append(
                [
                    f"{row.get('gene1', '')} - {row.get('gene2', '')}",
                    short.get(tier, "-") if tier in (1, 2, 3, 4) else "-",
                ]
            )
            supported = int(call.get("spanpairs") or 0) > 0
            details.append(
                _detail(
                    f"fusion-{index}",
                    title,
                    [
                        ("Gener", title),
                        ("Effekt", (call.get("effect") or "-") if supported else "NA"),
                        ("Fusionspunkter", locus if supported else "NA"),
                        ("Antal läsningar", call.get("spanreads")),
                        ("Antal läs-par", call.get("spanpairs")),
                        (
                            "Längsta ankarsekvens",
                            f"{call['longestanchor']} bp" if call.get("longestanchor") else "NA",
                        ),
                        (
                            "Klassificering",
                            _format_classification(
                                tier, (context.get("class_desc") or TIER_DESC).get(tier)
                            ),
                        ),
                        ("Kommentar", _comment(row)),
                    ],
                )
            )
        add_table(
            "fusions",
            "Kliniskt relevanta fusioner",
            [
                "Fusion/exon skipping" if sample.get("asp_id") == "fusionrna" else "Fusion",
                "Klassificering",
            ],
            rows,
            "FUSION",
        )
