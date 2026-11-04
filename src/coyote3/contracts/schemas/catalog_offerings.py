"""Public offering snapshots and independently configured service prices."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer

from coyote3.contracts.schemas.base import _StrictDocBase


class CatalogPriceDoc(_StrictDocBase):
    """A public offering price in one explicitly declared currency."""

    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    kind: Literal["fixed", "starting", "estimated"] = "fixed"
    conditions: str = ""

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Store exact decimal currency values as BSON-compatible text."""
        return format(value, ".2f")


class CatalogGeneScopeDoc(_StrictDocBase):
    """Published effective genes for one analysis and gene-list revision."""

    list_id: str
    label: str
    revision: int = Field(ge=1)
    analysis: str
    genes: list[str]
    excluded_gene_count: int = Field(ge=0)


class CatalogOfferingDoc(_StrictDocBase):
    """Allowlisted service information independent of operational configuration storage."""

    offering_id: str
    title: str
    group_id: str
    group_label: str
    diagnosis_id: str
    diagnosis_label: str
    modality: Literal["dna", "rna"]
    family: str
    assay_id: str
    assay_label: str
    assay_display_name: str = ""
    description: str = ""
    analysis: list[str]
    price: CatalogPriceDoc | None = None
    pricing_message: str = "Contact for pricing"
    turnaround: str = ""
    input_material: list[str] = Field(default_factory=list)
    sample_modes: list[str] = Field(default_factory=list)
    platform: str = ""
    read_length: int | None = Field(default=None, ge=0)
    read_mode: str = ""
    covered_gene_count: int | None = Field(default=None, ge=0)
    report_deliverables: list[str] = Field(default_factory=list)
    methodology: str = ""
    limitations: str = ""
    ordering_information: str = ""

    gene_scopes: list[CatalogGeneScopeDoc] = Field(default_factory=list)


class CatalogNavigationNodeDoc(_StrictDocBase):
    """Public presentation for one section, group or diagnosis in the reviewed tree."""

    node_id: str
    parent_id: str | None = None
    offering_id: str | None = None
    label: str
    title: str
    description: str = ""
    subheading: str = ""
    input_material: list[str] = Field(default_factory=list)
    sample_modes: list[str] = Field(default_factory=list)
    analysis: list[str] = Field(default_factory=list)
    turnaround: str = ""
    report_deliverables: list[str] = Field(default_factory=list)
    clinical_indications: list[str] = Field(default_factory=list)
    limitations: str = ""
    public_notes: str = ""
    methodology: str = ""
    ordering_information: str = ""
    price: CatalogPriceDoc | None = None
    pricing_message: str = ""
    clear_fields: list[str] = Field(default_factory=list)


class CatalogDiscoveryDoc(_StrictDocBase):
    """Published services used by both diagnosis-first and assay-first navigation."""

    version: int = Field(ge=0)
    header: str
    description: str = ""
    offerings: list[CatalogOfferingDoc] = Field(default_factory=list)
    navigation: list[CatalogNavigationNodeDoc] = Field(default_factory=list)
