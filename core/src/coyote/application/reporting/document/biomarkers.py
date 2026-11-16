# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Biomarker tables and detail cards."""

from coyote.application.reporting.ordering import analysis_priority

from .formatting import _detail, _table
from .sections import ReportSections


class BiomarkerSections:
    """Present measured biomarkers and assessments without deriving missing results."""

    def __init__(self, document: ReportSections) -> None:
        """Bind the current document's resolved inputs and output sections."""
        self.document = document

    def append(self) -> list[str]:
        """Append configured biomarker evidence and return its analysis ordering keys."""
        context = self.document.context
        empty = self.document.empty
        sections = self.document.sections
        details = self.document.details
        data = context.get("report_sections_data") or {}
        enabled = context.get("report_sections") or []
        rows = []
        row_analyses = []
        methods_by_analysis = [
            ("HRD", ["HRD"]),
            ("MSI", ["MSIP"] if context["sample"].get("paired") else ["MSIS"]),
            ("TMB", ["TMB"]),
            ("BIOMARKER", [None]),
        ]
        order = ((context.get("assay_config") or {}).get("reporting") or {}).get(
            "summary_table_order"
        ) or []
        for analysis, methods in methods_by_analysis:
            if analysis not in enabled:
                continue
            found = False
            for index, row in enumerate(
                data.get("biomarkers" if analysis == "BIOMARKER" else analysis.lower()) or []
            ):
                for method in methods:
                    measurement = row if method is None else row.get(method)
                    if not measurement:
                        continue
                    found = True
                    name = method or row.get("biomarker") or "Biomarkör"
                    assessment = (measurement.get("clinical_assessment") or {}).get(
                        "value"
                    ) or "Ej bedömd"
                    rows.append([name, assessment])
                    row_analyses.append(analysis)
                    if analysis == "HRD":
                        fields = [
                            (label, measurement.get(key))
                            for label, key in [
                                ("Summa", "sum"),
                                ("TAI", "tai"),
                                ("HRD", "hrd"),
                                ("LST", "lst"),
                            ]
                        ]
                    elif analysis == "MSI":
                        fields = [
                            ("Andel", f"{measurement.get('per', '-')}%"),
                            (
                                "Instabila / totalt",
                                f"{measurement.get('som', '-')} / {measurement.get('tot', '-')}",
                            ),
                        ]
                    elif analysis == "TMB":
                        fields = [
                            (
                                "TMB",
                                f"{measurement.get('value', '-')} {measurement.get('unit') or 'mut/Mb'}",
                            )
                        ]
                    else:
                        fields = [
                            (key, value)
                            for key, value in row.items()
                            if key
                            not in {
                                "_id",
                                "SAMPLE_ID",
                                "name",
                                "biomarker",
                                "clinical_assessment",
                                "assessment_history",
                            }
                        ]
                    if method is not None:
                        fields.append(("Klinisk bedömning", assessment))
                    if fields:
                        details.append(
                            _detail(
                                f"biomarker-{analysis.lower()}-{index}",
                                f"{name} · {row.get('name') or 'Biomarkör'}",
                                fields,
                            )
                        )
            if not found:
                sections.append(
                    {"key": f"empty-{analysis.lower()}", "kind": "text", "text": empty[analysis]}
                )
        if rows:
            sections.append(
                _table(
                    "biomarkers",
                    "Kliniskt relevanta biomarkörer",
                    ["Biomarkör", "Klinisk bedömning"],
                    [
                        row
                        for _, row in sorted(
                            zip(row_analyses, rows),
                            key=lambda entry: analysis_priority([entry[0]], order),
                        )
                    ],
                )
            )
        return row_analyses
