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


class ApiPublicAssayCatalogMatrixContextPayload(ApiModel):
    modalities: JsonDict = Field(default_factory=dict)
    order: list[str] = Field(default_factory=list)
    columns: list[JsonDict] = Field(default_factory=list)
    mod_spans: JsonDict = Field(default_factory=dict)
    cat_spans: JsonDict = Field(default_factory=dict)
    genes: list[str] = Field(default_factory=list)
    matrix: JsonDict = Field(default_factory=dict)


class ApiPublicAssayCatalogContextPayload(ApiModel):
    meta: JsonDict = Field(default_factory=dict)
    order: list[str] = Field(default_factory=list)
    modalities: JsonDict = Field(default_factory=dict)
    selected_mod: str | None = None
    categories: list[JsonDict] = Field(default_factory=list)
    selected_cat: str | None = None
    selected_isgl: str | None = None
    right: JsonDict = Field(default_factory=dict)
    gene_mode: str | None = None
    genes: list[JsonDict] = Field(default_factory=list)
    stats: JsonDict = Field(default_factory=dict)


class ApiPublicAssayCatalogCsvContextPayload(ApiModel):
    filename: str
    content: str
