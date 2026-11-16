# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validated presentation settings independent of clinical finding selection."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from coyote.config.factory_defaults import factory_value

ReportMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class EmptyResultMessages(BaseModel):
    """Plain text shown when an enabled report section has no reportable findings."""

    model_config = ConfigDict(extra="forbid")

    SNV: ReportMessage = factory_value("reporting.empty_results.SNV")
    GERMLINE_SNV: ReportMessage = factory_value("reporting.empty_results.GERMLINE_SNV")
    CNV: ReportMessage = factory_value("reporting.empty_results.CNV")
    TRANSLOCATION: ReportMessage = factory_value("reporting.empty_results.FUSION")
    FUSION: ReportMessage = factory_value("reporting.empty_results.FUSION")
    HRD: ReportMessage = factory_value("reporting.empty_results.BIOMARKER")
    MSI: ReportMessage = factory_value("reporting.empty_results.BIOMARKER")
    TMB: ReportMessage = factory_value("reporting.empty_results.BIOMARKER")
    BIOMARKER: ReportMessage = factory_value("reporting.empty_results.BIOMARKER")
    PGX: ReportMessage = factory_value("reporting.empty_results.PGX")


class ReportPresentation(BaseModel):
    """Modern report wording supplied by a trusted host or a local SDK caller."""

    model_config = ConfigDict(extra="forbid")

    empty_results: EmptyResultMessages = Field(default_factory=EmptyResultMessages)
