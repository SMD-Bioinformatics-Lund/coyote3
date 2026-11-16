# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Panel references, numbered gene matrices and classification legend."""

from urllib.parse import quote

from coyote.application.reporting.report_renderer import _format_tier

from .formatting import (
    _table,
)
from .sections import ReportSections


class ReportReferences:
    """Append numbered gene lists, panel URLs and classification references."""

    def __init__(self, document: ReportSections) -> None:
        """Bind the current document's resolved inputs and output sections."""
        self.document = document

    def append(self) -> None:
        """Append the existing reference content and preserve numbered-table order."""
        context = self.document.context
        analyte = self.document.analyte
        sample = self.document.sample
        sections = self.document.sections
        table_number = 1
        for index, (name, genes) in enumerate(
            (context.get("genes_covered_in_panel") or {}).items()
        ):
            if name != sample.get("asp_id"):
                covered = genes.get("covered") or []
                sections.append(
                    {
                        "key": f"gene-list-{index}",
                        "kind": "compact_table",
                        "caption": (
                            f"Tabell {table_number}: Gener inkluderade i {name} insilico-panel"
                        ),
                        "items": list(covered),
                        "columns": 15,
                    }
                )
                table_number += 1
        branding = context.get("branding") or {}
        public_url = branding.get("public_base_url")
        assay_id = sample.get("asp_id")
        if analyte == "dna" and public_url and assay_id:
            lines = [
                "För analysens genlista, se:",
                f"{public_url}/public/asp/{quote(str(assay_id), safe='')}/genes",
            ]
            applied = {
                name: genes
                for name, genes in (context.get("genes_covered_in_panel") or {}).items()
                if name != assay_id
            }
            if applied:
                lines.extend(["", "För de in silico-genlistor som tillämpats i denna rapport, se:"])
                for name, genes in applied.items():
                    if genes.get("adhoc"):
                        lines.append(f"{name}: provspecifik genlista (ingen publik URL).")
                    else:
                        lines.append(
                            f"{name}: {public_url}/public/genelists/{quote(str(name), safe='')}/view"
                            f"?assay={quote(str(assay_id), safe='')}"
                        )
            sections.append(
                {
                    "key": "panel-reference",
                    "kind": "description",
                    "heading": "",
                    "text": {"sv": "\n".join(lines)},
                }
            )
        if not context.get("germline") or analyte == "rna":
            legend = {
                1: "Variant av stark klinisk signifikans (genmutationer som är diagnostiska, behandlingsstyrande eller riskstratifierande enligt gällande riktlinjer)",
                2: "Variant av potentiell klinisk signifikans (mutationer i gener beskrivna i ett flertal publikationer)",
                3: "Variant av oklar klinisk signifikans (mutationer i gener beskrivna i ett fåtal publikationer)",
                4: "Variant bedömd som benign eller sannolikt benign",
            }
            if analyte == "rna":
                legend.update(
                    {
                        1: "Variant av stark klinisk signifikans (innefattar varianter i gener som finns med i internationella/nationella riktlinjer)",
                        2: "Variant av potentiell klinisk signifikans (innefattar varianter i gener som finns med i publikationer)",
                        3: "Variant av oklar klinisk signifikans (innefattar varianter i gener i få eller inga publikationer)",
                    }
                )
            sections.append(
                _table(
                    "classification",
                    "",
                    ["", ""],
                    [[_format_tier(tier), text] for tier, text in legend.items()],
                    caption=(
                        f"Tabell {table_number}: Förklaring av klassificering"
                        if analyte == "dna"
                        else "Tabell: Förklaring av klassificering"
                    ),
                    style="reference",
                    show_header=False,
                    column_options={"0": {"width": 12}, "1": {"width": 88}},
                )
            )
            sections.append(
                {
                    "key": "references",
                    "kind": "references",
                    "text": "[1] Standards and guidelines for the interpretation and reporting of sequence variants in cancer. Li et al, Journal of Molecular Diagnostics, 2017.",
                }
            )
