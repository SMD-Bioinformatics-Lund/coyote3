"""Validated presentation settings independent of clinical finding selection."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ReportMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class EmptyResultMessages(BaseModel):
    """Plain text shown when an enabled report section has no reportable findings."""

    model_config = ConfigDict(extra="forbid")

    SNV: ReportMessage = "Inga detekterade mutationer"
    GERMLINE_SNV: ReportMessage = "Inga detekterade germline-mutationer"
    CNV: ReportMessage = "Inga detekterade kopietalsförändringar."
    TRANSLOCATION: ReportMessage = "Inga detekterade fusioner"
    FUSION: ReportMessage = "Inga detekterade fusioner"
    HRD: ReportMessage = "Inga rapporterbara biomarkörresultat"
    MSI: ReportMessage = "Inga rapporterbara biomarkörresultat"
    TMB: ReportMessage = "Inga rapporterbara biomarkörresultat"
    BIOMARKER: ReportMessage = "Inga rapporterbara biomarkörresultat"
    PGX: ReportMessage = "Inga rapporterbara farmakogenomiska resultat"


class ReportPresentation(BaseModel):
    """Modern report wording supplied by a trusted host or a local SDK caller."""

    model_config = ConfigDict(extra="forbid")

    empty_results: EmptyResultMessages = Field(default_factory=EmptyResultMessages)
