# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Shared state for composing one report document."""

from typing import Any

from pydantic import BaseModel, Field

from coyote.application.reporting.presentation import ReportPresentation
from coyote.domain.common.reporting import TIER_SHORT_DESC

from .formatting import _table


class ReportSections(BaseModel):
    """Collect one document's ordered summary sections and finding details."""

    context: dict[str, Any]
    analyte: str
    presentation: ReportPresentation
    sections: list[dict[str, Any]] = Field(default_factory=list)
    details: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def sample(self) -> dict[str, Any]:
        """Return the reviewed sample metadata."""
        return self.context["sample"]

    @property
    def config(self) -> dict[str, Any]:
        """Return the resolved assay configuration."""
        return self.context["assay_config"]

    @property
    def data(self) -> dict[str, Any]:
        """Return the selected findings for this report."""
        return self.context.get("report_sections_data") or {}

    @property
    def enabled(self) -> list[str]:
        """Return the configured report analyses in their original order."""
        return self.context.get("report_sections") or []

    @property
    def empty(self) -> dict[str, str]:
        """Return approved empty-result wording by analysis."""
        return self.presentation.empty_results.model_dump()

    @property
    def short(self) -> dict[int, str]:
        """Return short classification labels supplied by the report context."""
        return self.context.get("class_desc_short") or TIER_SHORT_DESC

    def add_table(
        self, key: str, heading: str, columns: list[str], rows: list[list[Any]], empty_key: str
    ) -> None:
        """Append a result table with its approved empty-result wording.

        Args:
            key: Stable section identifier.
            heading: Existing clinical section title.
            columns: Ordered display labels.
            rows: Selected finding values in column order.
            empty_key: Analysis key identifying its empty-result message.
        """
        self.sections.append(_table(key, heading, columns, rows, empty_text=self.empty[empty_key]))
