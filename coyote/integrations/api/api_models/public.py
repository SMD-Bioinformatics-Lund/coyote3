"""Public payload models used by Flask public blueprint routes."""

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiPublicGenelistViewContextPayload(ApiModel):
    genelist: JsonDict = Field(default_factory=dict)
    selected_assay: str | None = None
    filtered_genes: list[str] = Field(default_factory=list)
    germline_genes: list[str] = Field(default_factory=list)
    is_public: bool = True


class ApiPublicAspGenesPayload(ApiModel):
    asp_id: str
    gene_details: list[JsonDict] = Field(default_factory=list)
    germline_gene_symbols: list[str] = Field(default_factory=list)


class ApiPublicAssayCatalogGenesViewPayload(ApiModel):
    gene_symbols: list[str] = Field(default_factory=list)

