"""Canonical public router module."""

from __future__ import annotations

import csv
import datetime
import io
from copy import deepcopy
from pathlib import Path

import yaml
from fastapi import APIRouter, Query

from api.app.container import store, util
from api.app.deps.services import get_public_catalog_service
from api.app.http import api_error as _api_error
from api.app.runtime_state import app as runtime_app
from api.application.public.catalog import PublicCatalogService
from api.config.app_config import REPO_ROOT
from api.contracts.public import (
    PublicAboutPayload,
    PublicAspGenesPayload,
    PublicAssayCatalogGenesCsvPayload,
    PublicAssayCatalogMatrixPayload,
    PublicAssayCatalogPayload,
    PublicContactPayload,
    PublicFilterFlagMetadataPayload,
    PublicGenelistViewPayload,
    PublicGeneSymbolsPayload,
)
from api.interfaces.http.tags import TAG_PUBLIC

router = APIRouter(tags=[TAG_PUBLIC])
__all__ = ["router", "PublicCatalogService"]


def _load_filter_flag_metadata() -> dict:
    metadata_path = Path(REPO_ROOT) / "api" / "config" / "filter_flag_metadata.yaml"
    if not metadata_path.exists():
        return {"exact": {}, "prefixes": {}, "terms": {}}
    with metadata_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return {
        "exact": raw.get("exact") or {},
        "prefixes": raw.get("prefixes") or {},
        "terms": raw.get("terms") or {},
    }


@router.get("/api/v1/public/contact", response_model=PublicContactPayload)
def public_contact_read():
    """Return center-owned public contact and support metadata."""
    return _public_contact_payload()


@router.get("/api/v1/public/about", response_model=PublicAboutPayload)
def public_about_read():
    """Return public application, support, and reference-version metadata."""
    payload = _public_contact_payload()
    payload.update(
        {
            "application": {
                "name": "Coyote3",
                "version": runtime_app.config.get("APP_VERSION"),
                "environment": runtime_app.config.get("ENV_NAME"),
                "script_name": runtime_app.config.get("SCRIPT_NAME"),
                "description": (
                    "Clinical genomics interpretation, sample review, "
                    "classification, and traceable reporting workspace."
                ),
            },
            "software": _public_software_versions(),
            "references": _public_reference_versions(),
            "databases": {
                "primary": runtime_app.config.get("COYOTE3_DB"),
                "bam_service": runtime_app.config.get("BAM_DB"),
                "knowledgebases": {
                    "oncokb_public": runtime_app.config.get("ONCOKB_BASE_URL"),
                    "clinpgx_public": runtime_app.config.get("CLINPGX_BASE_URL"),
                },
            },
        }
    )
    return util.common.convert_to_serializable(payload)


def _public_contact_payload() -> dict:
    """Build center-owned public contact and support metadata."""
    contact = runtime_app.config.get("CONTACT") or {}
    organization = dict(contact.get("organization") or {})
    organization.setdefault("name", runtime_app.config.get("ORGANIZATION_NAME") or "Coyote3")
    payload = {
        "organization": organization,
        "support": dict(contact.get("support") or {}),
        "codebase": dict(contact.get("codebase") or {}),
        "contacts": list(contact.get("contacts") or []),
        "links": list(contact.get("links") or []),
        "hours": list(contact.get("hours") or []),
        "meta": dict(contact.get("meta") or {}),
    }
    return util.common.convert_to_serializable(payload)


def _public_software_versions() -> dict:
    """Return software versions observed in stored sample metadata."""
    pipelines: dict[str, set[str]] = {}
    vep_versions: set[str] = set()
    try:
        collection = store.sample_repository.get_collection()
        cursor = collection.find(
            {},
            {"pipeline": 1, "pipeline_version": 1, "vep_version": 1},
        ).limit(1000)
        for sample in cursor:
            pipeline = str(sample.get("pipeline") or "").strip()
            pipeline_version = str(sample.get("pipeline_version") or "").strip()
            if pipeline:
                pipelines.setdefault(pipeline, set())
                if pipeline_version:
                    pipelines[pipeline].add(pipeline_version)
            vep_version = str(sample.get("vep_version") or "").strip()
            if vep_version:
                vep_versions.add(vep_version)
    except Exception as exc:  # pragma: no cover - defensive public metadata path
        runtime_app.logger.warning("Could not build public software versions: %s", exc)
    return {
        "pipelines": {key: sorted(values) for key, values in sorted(pipelines.items())},
        "vep": sorted(vep_versions),
    }


def _public_reference_versions() -> dict:
    """Return reference database versions observed in samples and VEP metadata."""
    database_versions: dict[str, set[str]] = {}
    vep_metadata_versions: set[str] = set()
    try:
        cursor = (
            store.sample_repository.get_collection()
            .find(
                {"database_versions": {"$type": "object"}},
                {"database_versions": 1},
            )
            .limit(1000)
        )
        for sample in cursor:
            for name, version in dict(sample.get("database_versions") or {}).items():
                key = str(name).strip()
                value = str(version).strip()
                if key and value:
                    database_versions.setdefault(key, set()).add(value)
    except Exception as exc:  # pragma: no cover - defensive public metadata path
        runtime_app.logger.warning("Could not build public sample reference versions: %s", exc)
    try:
        for value in store.vep_metadata_repository.get_collection().distinct("vep_id"):
            normalized = str(value).strip()
            if normalized:
                vep_metadata_versions.add(normalized)
    except Exception as exc:  # pragma: no cover - defensive public metadata path
        runtime_app.logger.warning("Could not build public VEP metadata versions: %s", exc)
    return {
        "sample_database_versions": {
            key: sorted(values) for key, values in sorted(database_versions.items())
        },
        "vep_metadata": sorted(vep_metadata_versions),
    }


@router.get("/api/v1/public/filter-flags/metadata", response_model=PublicFilterFlagMetadataPayload)
def public_filter_flag_metadata_read():
    """Return center-configurable VCF filter flag metadata."""
    return util.common.convert_to_serializable(_load_filter_flag_metadata())


@router.get(
    "/api/v1/public/genelists/{genelist_id}/view_context", response_model=PublicGenelistViewPayload
)
def public_genelist_view_context_read(genelist_id: str, assay: str | None = None):
    """Return public view context for a genelist.

    Args:
        genelist_id: Genelist identifier to inspect.
        assay: Optional assay used to scope visible genes.

    Returns:
        dict: Public genelist view payload.
    """
    service = get_public_catalog_service()
    payload = service.genelist_view_context(genelist_id, assay)
    if not payload:
        raise _api_error(404, "Genelist not found")
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/public/asp/{asp_id}/genes", response_model=PublicAspGenesPayload)
def public_asp_genes_read(asp_id: str):
    """Return public genes for an assay panel.

    Args:
        asp_id: Assay-panel identifier to inspect.

    Returns:
        dict: Public assay-panel gene payload.
    """
    service = get_public_catalog_service()
    return util.common.convert_to_serializable(service.asp_genes_payload(asp_id))


@router.get(
    "/api/v1/public/assay-catalog/genes/{isgl_key}/view_context",
    response_model=PublicGeneSymbolsPayload,
)
def public_assay_catalog_isgl_genes_view_read(isgl_key: str):
    """Return public catalog genes for a catalog genelist.

    Args:
        isgl_key: Catalog genelist identifier to inspect.

    Returns:
        dict: Public gene-symbol payload.
    """
    service = get_public_catalog_service()
    return util.common.convert_to_serializable(service.assay_catalog_gene_symbols_payload(isgl_key))


@router.get(
    "/api/v1/public/assay-catalog-matrix/context", response_model=PublicAssayCatalogMatrixPayload
)
def public_assay_catalog_matrix_context_read(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    gene: str | None = None,
):
    """Return the public assay-catalog matrix payload.

    Returns:
        dict: Assay-catalog matrix payload.
    """
    service = get_public_catalog_service()
    vm = service.assay_catalog_matrix_payload(page=page, per_page=per_page, gene=gene)
    return util.common.convert_to_serializable(vm)


@router.get("/api/v1/public/assay-catalog/context", response_model=PublicAssayCatalogPayload)
def public_assay_catalog_context_read(
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    """Return public assay-catalog context for the selected modality/category."""
    service = get_public_catalog_service()
    catalog = service.load_catalog()
    order = service.modalities_order()
    if not order:
        raise _api_error(404, "Catalog not found")

    selected_mod = service.normalize_mod(mod) if mod else None
    selected_cat = cat if cat else None
    selected_isgl = isgl_key if isgl_key else None
    mods = catalog.get("modalities") or {}

    if not selected_mod:
        right = {
            "title": catalog.get("header") or "Assay Catalog",
            "description": catalog.get("description")
            or "Select a modality to explore available assays.",
            "input_material": None,
            "tat": None,
            "sample_modes": [],
            "analysis": [],
            "report_sections": [],
            "asp_id": None,
            "aspc_id": None,
            "aspc_ids": {},
            "subpanel_id": None,
            "asp": None,
            "clinical_indications": [],
            "limitations": None,
            "public_notes": None,
            "gene_lists": [],
        }
        gene_mode, genes, stats = (
            "covered",
            [],
            {"total": 0, "covered_total": 0, "germline_total": 0},
        )
    elif selected_mod and not selected_cat:
        right = service.hydrate_modality(selected_mod)
        gene_mode, genes, stats = service.resolve_gene_table(right.get("asp_id"), None)
    else:
        if selected_isgl:
            hydrated_cat = service.hydrate_category(
                selected_mod, selected_cat, selected_isgl, env="production"
            )
        else:
            hydrated_cat = service.hydrate_category(selected_mod, selected_cat, env="production")
        if not hydrated_cat:
            raise _api_error(404, "Category not found")
        right = {
            "title": hydrated_cat.get("title") or hydrated_cat.get("label"),
            "catalog_id": hydrated_cat.get("catalog_id"),
            "subheading": hydrated_cat.get("subheading"),
            "description": hydrated_cat.get("description"),
            "input_material": hydrated_cat.get("input_material"),
            "tat": hydrated_cat.get("tat"),
            "sample_modes": hydrated_cat.get("sample_modes") or [],
            "analysis": hydrated_cat.get("analysis") or [],
            "report_sections": hydrated_cat.get("report_sections") or [],
            "asp_id": hydrated_cat.get("asp_id"),
            "aspc_id": hydrated_cat.get("aspc_id"),
            "aspc_ids": hydrated_cat.get("aspc_ids") or {},
            "subpanel_id": hydrated_cat.get("subpanel_id"),
            "asp": hydrated_cat.get("asp"),
            "clinical_indications": hydrated_cat.get("clinical_indications") or [],
            "limitations": hydrated_cat.get("limitations"),
            "public_notes": hydrated_cat.get("public_notes"),
            "gene_lists": hydrated_cat.get("gene_lists") or [],
            "sample_query": hydrated_cat.get("sample_query"),
        }
        gene_mode, genes, stats = service.resolve_gene_table(
            hydrated_cat.get("asp_id"), selected_isgl
        )

    genes = service.apply_drug_info(genes=deepcopy(genes), druglist_name="drug_addon")
    vm = {
        "meta": {
            "version": catalog.get("version"),
            "last_updated": catalog.get("last_updated"),
            "maintainer": catalog.get("maintainer"),
            "header": catalog.get("header"),
            "description": catalog.get("description"),
            "nav_groups": catalog.get("nav_groups") or [],
        },
        "order": order,
        "modalities": mods,
        "selected_mod": selected_mod,
        "categories": service.categories_for(selected_mod) if selected_mod else [],
        "selected_cat": selected_cat,
        "selected_isgl": selected_isgl,
        "right": right,
        "gene_mode": gene_mode,
        "genes": genes,
        "stats": stats,
    }
    return util.common.convert_to_serializable(vm)


@router.get(
    "/api/v1/public/assay-catalog/genes.csv/context",
    response_model=PublicAssayCatalogGenesCsvPayload,
)
def public_assay_catalog_genes_csv_context_read(
    mod: str,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    """Return a CSV export payload for public assay-catalog genes."""
    service = get_public_catalog_service()
    selected_mod = service.normalize_mod(mod)
    if not selected_mod:
        raise _api_error(404, "Modality not found")

    if not cat:
        right = service.hydrate_modality(selected_mod)
        asp_id = right.get("asp_id")
    else:
        hydrated_cat = service.hydrate_category(selected_mod, cat, env="production")
        if not hydrated_cat:
            raise _api_error(404, "Category not found")
        asp_id = hydrated_cat.get("asp_id")

    mode, rows, _stats = service.resolve_gene_table(asp_id, isgl_key)

    sio = io.StringIO()
    writer = csv.writer(sio, lineterminator="\n")
    writer.writerow(
        ["HGNC_ID", "Gene_Symbol", "Chromosome", "Start", "End", "Gene_Type", "Drug Target"]
    )
    for gene in rows:
        writer.writerow(
            [
                (gene.get("hgnc_id") or "").replace("HGNC:", "HGNC:"),
                gene.get("hgnc_symbol") or gene.get("symbol") or "",
                gene.get("chromosome") or "",
                gene.get("start") or "",
                gene.get("end") or "",
                ",".join(gene.get("gene_type") or []),
                gene.get("drug_target") or "",
            ]
        )
    dt = datetime.date.today().isoformat()
    if not cat:
        label = f"{selected_mod}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    else:
        label = f"{selected_mod}.{cat}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    fname = f"{label}.{dt}.genes.csv"
    return {"filename": fname, "content": sio.getvalue()}
