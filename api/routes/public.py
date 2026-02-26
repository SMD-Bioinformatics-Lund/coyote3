"""Public read routes for Flask public blueprint pages."""

from __future__ import annotations

from coyote.extensions import store, util
from api.app import _api_error, app


@app.get("/api/v1/public/genelists/{genelist_id}/view_context")
def public_genelist_view_context_read(genelist_id: str, assay: str | None = None):
    genelist = store.isgl_handler.get_isgl(genelist_id, is_active=True)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    selected_assay = assay
    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])

    filtered_genes = all_genes
    germline_genes: list[str] = []
    if selected_assay and selected_assay in assays:
        panel = store.asp_handler.get_asp(selected_assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = (
            sorted(set(all_genes).intersection(panel_genes))
            if panel and panel.get("asp_family") not in ["WGS", "WTS"]
            else all_genes
        )

    return util.common.convert_to_serializable(
        {
            "genelist": genelist,
            "selected_assay": selected_assay,
            "filtered_genes": filtered_genes,
            "germline_genes": germline_genes,
            "is_public": True,
        }
    )


@app.get("/api/v1/public/asp/{asp_id}/genes")
def public_asp_genes_read(asp_id: str):
    gene_symbols, germline_gene_symbols = store.asp_handler.get_asp_genes(asp_id)
    gene_details = store.hgnc_handler.get_metadata_by_symbols(gene_symbols)
    return util.common.convert_to_serializable(
        {
            "asp_id": asp_id,
            "gene_details": gene_details,
            "germline_gene_symbols": germline_gene_symbols,
        }
    )


@app.get("/api/v1/public/assay-catalog/genes/{isgl_key}/view_context")
def public_assay_catalog_isgl_genes_view_read(isgl_key: str):
    isgl = store.isgl_handler.get_isgl(isgl_key) or {}
    gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()
    return util.common.convert_to_serializable({"gene_symbols": sorted(gene_symbols)})

