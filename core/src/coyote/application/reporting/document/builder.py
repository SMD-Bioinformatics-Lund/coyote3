# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Compose the smd-reports document from focused section builders."""

from typing import Any

from coyote.application.reporting.ordering import order_summary_tables
from coyote.application.reporting.presentation import ReportPresentation
from coyote.application.reporting.report_service import REPORT_PRESET
from coyote.version import __version__

from .biomarkers import BiomarkerSections
from .dna import DnaResultSections
from .formatting import _summary_text
from .metadata import _metadata
from .pharmacogenomics import PharmacogenomicSections
from .references import ReportReferences
from .rna import RnaResultSections
from .sections import ReportSections


class ReportDocumentBuilder:
    """Compose smd-reports documents from already selected clinical evidence."""

    def __init__(
        self,
        context: dict[str, Any],
        *,
        analyte: str,
        preview: bool,
        presentation: ReportPresentation,
    ) -> None:
        """Bind inputs without changing their clinical eligibility or wording.

        Args:
            context: Resolved findings, metadata, narrative and branding.
            analyte: DNA or RNA, expressed as dna or rna.
            preview: Whether to display the unsaved-report notice.
            presentation: Approved empty-result wording for enabled analyses.

        Raises:
            ValueError: The requested analyte is unsupported.
        """
        if analyte not in {"dna", "rna"}:
            raise ValueError("Report input requires a DNA or RNA analyte")
        self.context = context
        self.analyte = analyte
        self.preview = preview
        self.presentation = presentation

    def _question_heading(self, heading: str) -> str:
        """Use the patient-table question verbatim, or the diagnosis placeholder."""
        question = next(
            (
                field["value"]
                for field in self.metadata["fields"]
                if field["label"] == "Frågeställning"
            ),
            None,
        )
        return f"{heading} frågeställning {question or '<DIAGNOSIS>'}"

    def build(self) -> dict[str, Any]:
        """Build a fresh document, preserving section order and report provenance.

        Returns:
            JSON-compatible smd-reports document ready for validation.

        Raises:
            ValueError: A selected call, timestamp or embedded artwork is invalid.
        """
        self.metadata = _metadata(self.context, self.analyte)
        document = ReportSections(
            context=self.context, analyte=self.analyte, presentation=self.presentation
        )
        if self.preview:
            document.sections.append(
                {"key": "preview", "kind": "text", "text": "PREVIEW · UNSAVED REPORT"}
            )
        document.sections.append(
            {
                "key": "results",
                "kind": "text",
                "heading": self._question_heading("Analysresultat")
                if self.analyte == "dna"
                else "Analysresultat",
                "text": "",
            }
        )
        if self.analyte == "dna":
            DnaResultSections(document).append()
        else:
            RnaResultSections(document).append()
        biomarker_analyses = BiomarkerSections(document).append()
        PharmacogenomicSections(document).append()
        order_summary_tables(
            document.sections,
            (document.config.get("reporting") or {}).get("summary_table_order") or [],
            biomarker_analyses,
        )
        self._append_conclusion_and_details(document)
        ReportReferences(document).append()
        return self._document_payload(document)

    def _append_conclusion_and_details(self, document: ReportSections) -> None:
        """Append compact narrative, optional CNV profile and finding details."""
        context = document.context
        analyte = document.analyte
        data = document.data
        sections = document.sections
        details = document.details
        sections.append(
            {
                "key": "conclusion",
                "kind": "summary",
                "heading": self._question_heading("Slutsats"),
                "text": _summary_text(context),
                "format": "markdown",
            }
        )
        if data.get("cnv_profile_base64"):
            sections.append(
                {
                    "key": "cnv-profile",
                    "kind": "image",
                    "heading": "Kopietalsprofil, genomisk översikt",
                    "source": "data:image/png;base64," + data["cnv_profile_base64"],
                    "page_break_before": True,
                }
            )
        if details:
            details[0]["page_break_before"] = True
            details[0]["heading"] = (
                "Detekterade mutationer" if analyte == "dna" else "Detekterade fusioner"
            )
            sections.extend(details)
        sections.append(
            {
                "key": "description",
                "kind": "description",
                "heading": "Analysbeskrivning",
                "page_break_before": not bool(details),
                "text": {"sv": context.get("analysis_description") or ""},
                "format": "markdown",
            }
        )

    def _document_payload(self, document: ReportSections) -> dict[str, Any]:
        """Combine document sections, metadata, approved branding and provenance."""
        context = document.context
        analyte = document.analyte
        sample = document.sample
        config = document.config
        sections = document.sections
        branding = document.context.get("branding") or {}
        for key in ("coyote_logo", "center_logo", "accreditation_logo"):
            if branding.get(key) and not branding[key].startswith("data:image/"):
                raise ValueError("Report artwork must already be embedded")
        return {
            "preset": REPORT_PRESET,
            "analyte": analyte,
            "language": "sv",
            "title": (
                self._question_heading(
                    str((config.get("reporting") or {}).get("report_header") or "") + " -"
                )
                if analyte == "dna"
                else str(context.get("report_header") or "")
            ),
            "report": self.metadata,
            "layout": {"metadata_heading": "Patient/Analysinformation", "document_label": ""},
            "branding": {
                "application_name": "Coyote",
                "application_suffix": "4",
                "organization": branding.get("center_name")
                or context.get("organization_name")
                or "",
                "department": branding.get("center_department", ""),
                "address": branding.get("center_address", ""),
                "application_logo": branding.get("coyote_logo"),
                "center_logo": branding.get("center_logo"),
                "accreditation_logo": branding.get("accreditation_logo")
                if context.get("assay_accredited") is True
                else None,
                "accredited": context.get("assay_accredited") is True,
            },
            "provenance": {
                "application_name": "Coyote4",
                "application_version": __version__,
                "pipeline_name": str(sample.get("pipeline") or ""),
                "pipeline_version": str(sample.get("pipeline_version") or ""),
                "assay_name": str(sample.get("asp_id") or ""),
            },
            "sections": sections,
        }
