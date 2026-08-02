"""Software-owned application module definitions and route scopes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplicationModule:
    """Describe one independently available user-facing application module."""

    key: str
    control_field: str
    label: str
    description: str
    route_prefixes: tuple[str, ...] = ()
    route_fragments: tuple[str, ...] = ()


APPLICATION_MODULES: tuple[ApplicationModule, ...] = (
    ApplicationModule(
        key="dna_analysis",
        control_field="dna_analysis_enabled",
        label="DNA analysis",
        description="Small variants, CNVs, translocations, biomarkers, and coverage.",
        route_fragments=(
            "/small-variants",
            "/cnvs",
            "/translocations",
            "/biomarkers",
            "/coverage",
        ),
    ),
    ApplicationModule(
        key="rna_analysis",
        control_field="rna_analysis_enabled",
        label="RNA analysis",
        description="RNA fusion and expression analysis workflows.",
        route_fragments=("/fusions", "/expression"),
    ),
    ApplicationModule(
        key="reports",
        control_field="reports_enabled",
        label="Clinical reporting",
        description="Report preview, rendering, saving, and report retrieval.",
        route_fragments=("/reports",),
    ),
    ApplicationModule(
        key="variant_search",
        control_field="variant_search_enabled",
        label="Tiered variant search",
        description="Cross-sample search of tiered variants and annotation text.",
        route_prefixes=("/api/v1/common/search/tiered_variants",),
        route_fragments=("/reported_variants/",),
    ),
    ApplicationModule(
        key="knowledgebases",
        control_field="knowledgebases_enabled",
        label="Knowledgebases",
        description="Gene annotations and local or external knowledgebase lookups.",
        route_prefixes=("/api/v1/knowledgebases/", "/api/v1/common/gene/"),
        route_fragments=("/oncokb-public", "/clinpgx-public"),
    ),
    ApplicationModule(
        key="ingest_workspace",
        control_field="ingest_workspace_enabled",
        label="Ingest workspace",
        description="Manual sample-bundle upload, validation, and queue submission.",
        route_prefixes=("/api/v1/internal/ingest/",),
    ),
    ApplicationModule(
        key="assay_catalog",
        control_field="assay_catalog_enabled",
        label="Assay catalog",
        description="Public assay catalog, matrix, assay genes, and gene-list views.",
        route_prefixes=(
            "/api/v1/public/assay-catalog",
            "/api/v1/public/asp/",
            "/api/v1/public/genelists/",
        ),
    ),
)

APPLICATION_MODULE_BY_KEY = {module.key: module for module in APPLICATION_MODULES}
APPLICATION_MODULE_FIELDS = {module.control_field for module in APPLICATION_MODULES}


def modules_for_api_path(path: str) -> tuple[ApplicationModule, ...]:
    """Return every module governing an API path.

    A route can require more than one module. For example, an OncoKB lookup for
    a small variant requires both DNA analysis and knowledgebase availability.
    """
    return tuple(
        module
        for module in APPLICATION_MODULES
        if any(path.startswith(prefix) for prefix in module.route_prefixes)
        or any(fragment in path for fragment in module.route_fragments)
    )
