#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
This module defines Flask view functions for handling error screens and sample comment
operations within the Coyote3 project. It includes routes for displaying errors, adding,
hiding, and unhiding sample comments, and retrieving gene lists for samples. Access control
and user authentication are enforced via decorators.
"""

from flask import Response, redirect, request, url_for, flash, abort
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.blueprints.common.forms import TieredVariantSearchForm
from coyote.extensions import store, util
from flask import render_template
from flask_login import current_user
import traceback
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
import json
from flask_login import login_required
from copy import deepcopy
from typing import Any


@common_bp.route(
    "/dna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_dna_sample_comment",
)
@common_bp.route(
    "/rna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_rna_sample_comment",
)
@common_bp.route("/sample/<string:sample_id>/sample_comment", methods=["POST"])
@require_sample_access("sample_id")
@require("add_sample_comment", min_role="user", min_level=9)
def add_sample_comment(sample_id: str) -> Response:
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    doc = util.bpcommon.create_comment_doc(data, key="sample_comment")
    store.sample_handler.add_sample_comment(sample_id, doc)
    flash("Sample comment added", "green")
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@require_sample_access("sample_id")
@require("hide_sample_comment", min_role="manager", min_level=99)
def hide_sample_comment(sample_id: str) -> Response:
    """
    Hides a sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.hide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_by_id(sample_id)

    if sample.get("omics_layer", "").lower() == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif sample.get("omics_layer", "").lower() == "rna":
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))
    else:
        app.logger.info(
            f"Unrecognized omics type {sample['name']}! Unable to redirect to the sample page"
        )
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@require_sample_access("sample_id")
@require("unhide_sample_comment", min_role="manager", min_level=99)
def unhide_sample_comment(sample_id: str) -> Response:
    """
    Unhides a previously hidden sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.unhide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_by_id(sample_id)
    if sample.get("omics_layer", "").lower() == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif sample.get("omics_layer", "").lower() == "rna":
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))
    else:
        app.logger.info(
            f"Unrecognized omics type {sample['name']}! Unable to redirect to the sample page"
        )
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


@common_bp.route(
    "/dna/<string:sample_id>/var/<string:var_id>/classify",
    methods=["POST"],
    endpoint="classify_variant",
)
@common_bp.route(
    "/dna/<string:sample_id>/fus/<string:fus_id>/classify",
    methods=["POST"],
    endpoint="classify_fusion",
)
@require(permission="assign_tier", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def classify_variant(
    sample_id: str, var_id: str | None = None, fus_id: str | None = None
) -> Response:
    """
    Classify a DNA variant or RNA fusion from shared form payload.
    """
    if request.endpoint == "common_bp.classify_variant":
        id = var_id or request.view_args.get("var_id")
    elif request.endpoint == "common_bp.classify_fusion":
        id = fus_id or request.view_args.get("fus_id")
    else:
        id = var_id or fus_id

    form_data = request.form.to_dict()
    class_num = util.common.get_tier_classification(form_data)
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if class_num != 0:
        store.annotation_handler.insert_classified_variant(
            variant, nomenclature, class_num, form_data
        )

    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))

    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@common_bp.route(
    "/dna/<string:sample_id>/var/<string:var_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_variant",
)
@common_bp.route(
    "/dna/<string:sample_id>/fus/<string:fus_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_fusion",
)
@require(permission="remove_tier", min_role="admin")
@require_sample_access("sample_id")
def remove_classified_variant(
    sample_id: str, var_id: str | None = None, fus_id: str | None = None
) -> Response:
    """
    Remove a classified DNA variant or RNA fusion.
    """
    if request.endpoint == "common_bp.remove_classified_variant":
        id = var_id or request.view_args.get("var_id")
    elif request.endpoint == "common_bp.remove_classified_fusion":
        id = fus_id or request.view_args.get("fus_id")
    else:
        id = var_id or fus_id
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)

    delete_result = store.annotation_handler.delete_classified_variant(
        variant, nomenclature, form_data
    )
    app.logger.debug(delete_result)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@common_bp.route(
    "/dna/<string:sample_id>/var/<string:var_id>/add_variant_comment",
    methods=["POST"],
    endpoint="add_variant_comment",
)
@common_bp.route(
    "/dna/<string:sample_id>/cnv/<string:cnv_id>/add_cnv_comment",
    methods=["POST"],
    endpoint="add_cnv_comment",
)
@common_bp.route(
    "/dna/<string:sample_id>/fusion/<string:fus_id>/add_fusion_comment",
    methods=["POST"],
    endpoint="add_fusion_comment",
)
@common_bp.route(
    "/dna/<string:sample_id>/translocation/<string:transloc_id>/add_translocation_comment",
    methods=["POST"],
    endpoint="add_translocation_comment",
)
@require("add_variant_comment", min_role="user", min_level=9)
@require_sample_access("sample_id")
def add_var_comment(
    sample_id: str,
    var_id: str | None = None,
    cnv_id: str | None = None,
    fus_id: str | None = None,
    transloc_id: str | None = None,
) -> Response | str:
    """
    Add a comment to a variant, CNV, fusion, or translocation.
    """
    id = (
        var_id
        or cnv_id
        or fus_id
        or transloc_id
        or request.view_args.get("var_id")
        or request.view_args.get("cnv_id")
        or request.view_args.get("fus_id")
        or request.view_args.get("transloc_id")
    )

    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    doc = util.bpcommon.create_comment_doc(form_data, nomenclature=nomenclature, variant=variant)
    _type = form_data.get("global", None)
    if _type == "global":
        store.annotation_handler.add_anno_comment(doc)
        flash("Global comment added", "green")

    if nomenclature == "f":
        if _type != "global":
            store.fusion_handler.add_fusion_comment(id, doc)
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))
    elif nomenclature == "t":
        if _type != "global":
            store.transloc_handler.add_transloc_comment(id, doc)
        return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=id))
    elif nomenclature == "cn":
        if _type != "global":
            store.cnv_handler.add_cnv_comment(id, doc)
        return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=id))
    else:
        if _type != "global":
            store.variant_handler.add_var_comment(id, doc)

    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@common_bp.route("/<string:sample_id>/<string:sample_assay>/genes", methods=["POST"])
def get_sample_genelists(sample_id: str, sample_assay: str) -> str:
    """
    Retrieves and decrypts gene list and panel document data from the request form, then renders the 'sample_genes.html' template with the provided sample information.

    Args:
        sample_id (Any): The identifier for the sample.
        sample_assay (Any): The assay type or identifier for the sample.

    Returns:
        str: Rendered HTML content for the 'sample_genes.html' template.

    Raises:
        KeyError: If required form fields ('enc_genelists' or 'enc_panel_doc') are missing.
        Exception: If decryption or JSON decoding fails.
    """
    enc_genelists = request.form.get("enc_genelists")
    enc_panel_doc = request.form.get("enc_panel_doc")
    enc_sample_filters = request.form.get("enc_sample_filters")

    fernet_obj = app.config.get("FERNET")

    genelists = json.loads(fernet_obj.decrypt(enc_genelists.encode()))
    panel_doc = json.loads(fernet_obj.decrypt(enc_panel_doc.encode()))

    sample_filters = json.loads(fernet_obj.decrypt(enc_sample_filters.encode()))
    adhoc_genes = sample_filters.pop("adhoc_genes", "")
    if adhoc_genes:
        filter_gl = sample_filters.get("genelists", [])
        filter_gl.append(adhoc_genes.get("label", "Adhoc"))
        sample_filters["genelists"] = filter_gl

    return render_template(
        "sample_genes.html",
        sample=sample_id,
        genelists=genelists,
        asp_config=panel_doc,
        sample_filters=sample_filters,
    )


@common_bp.route("/public/gene/<string:id>/info", endpoint="public_gene_info", methods=["GET"])
@common_bp.route("/gene/<string:id>/info", endpoint="gene_info", methods=["GET"])
def gene_info(id: str) -> str:
    """
    Fetches and displays detailed information about a gene based on its HGNC ID.

    Args:
        hgnc_id (str): The HGNC ID of the gene to retrieve information for.
    Returns:
        str: Rendered HTML content for the 'gene_info.html' template.
    """

    if id.isnumeric():
        gene = store.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=id)
    else:
        gene = store.hgnc_handler.get_metadata_by_symbol(symbol=id)

    return render_template("gene_info.html", gene=gene)


@common_bp.route("/reported_variants/variant/<string:variant_id>/<int:tier>", methods=["GET"])
@login_required
@require("view_gene_annotations", min_role="user", min_level=9)
def list_samples_with_tiered_variant(variant_id: str, tier: int):
    """
    Show reported variants across samples that match this variant identity and tier.
    """
    variant = store.variant_handler.get_variant(variant_id)
    if not variant:
        abort(404)

    csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}

    gene = csq.get("SYMBOL")
    simple_id = variant.get("simple_id")
    simple_id_hash = variant.get("simple_id_hash")
    hgvsc = csq.get("HGVSc")
    hgvsp = csq.get("HGVSp")

    # ---- build OR conditions ----
    or_conditions = []
    if simple_id or simple_id_hash:
        if simple_id_hash:
            or_conditions.append({"simple_id_hash": simple_id_hash})
        elif simple_id:
            or_conditions.append({"simple_id": simple_id})
    else:
        if hgvsc:
            or_conditions.append({"hgvsc": hgvsc})
        elif hgvsp:
            or_conditions.append({"hgvsp": hgvsp})

    if not gene or not or_conditions:
        return render_template(
            "tiered_variant_info.html",
            variant=variant,
            docs=[],
            error="Variant has insufficient identity fields",
        )

    # ---- ONE final query ----
    query = {
        "gene": gene,
        "$or": or_conditions,
    }

    docs = store.reported_variants_handler.list_reported_variants(query)

    # Enrich docs with sample details, variant details, report details
    docs = util.bpcommon.enrich_reported_variant_docs(deepcopy(docs))

    return render_template(
        "tiered_variant_info.html",
        docs=docs,
        variant=variant,
        tier=tier,
    )


@common_bp.route("/search/tiered_variants", methods=["GET", "POST"])
@require("view_gene_annotations", min_role="user", min_level=9)
def search_tiered_variants():
    """
    Search reported variants across samples by gene name, variant id, HGVSc, or HGVSp.
    """
    form = TieredVariantSearchForm()
    form.assay.choices = store.asp_handler.get_all_asp_groups()

    limit_entries = app.config.get("TIERED_VARIANT_SEARCH_LIMIT", 1000)
    search_str = None
    search_mode = form.search_options.default
    include_annotation_text = form.include_annotation_text.default
    assays = form.assay.default

    if request.method == "POST":
        if form.validate_on_submit():
            search_str = form.variant_search.data.strip()
            search_mode = form.search_options.data
            include_annotation_text: bool = form.include_annotation_text.data
            assays: list[Any] | None = form.assay.data or None
        else:
            flash(form.variant_search.errors[0], "red")

    # Allow GET deep-links (from variant pages etc.)
    if request.method == "GET":
        qs = request.args

        # search string
        if qs.get("search_str"):
            search_str = qs.get("search_str", "").strip()
            form.variant_search.data = search_str

        # mode (gene / variant / transcript / etc)
        if qs.get("search_mode"):
            search_mode = qs.get("search_mode")
            form.search_options.data = search_mode

        # checkbox
        if qs.get("include_annotation_text") is not None:
            include_annotation_text = qs.get("include_annotation_text") in (
                "1",
                "true",
                "True",
                "yes",
                "on",
            )
            form.include_annotation_text.data = include_annotation_text

        # assays (multi)
        assays_qs = qs.getlist("assay")
        if assays_qs:
            assays = assays_qs
            form.assay.data = assays

    docs_found = store.annotation_handler.find_variants_by_search_string(
        search_str=search_str,
        search_mode=search_mode,
        include_annotation_text=include_annotation_text,
        assays=assays,
        limit=limit_entries,
    )

    tier_stats = {"total": {}, "by_assay": {}}
    if search_mode != "variant" and search_str:
        tier_stats = store.annotation_handler.get_tier_stats_by_search(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,  # list or None
        )

    # Search in reported docs
    sample_tagged_docs = []

    # remove text only annotations that are already associated with variants
    _annotation_text_oids_associated_with_variants: set[str] = set()

    for doc in docs_found:
        _doc = deepcopy(doc)
        _sample_oids = {}
        _reported_docs = []

        query = {"annotation_oid": doc["_id"]}

        _reported_docs = store.reported_variants_handler.list_reported_variants(query)

        for _reported_doc in _reported_docs:
            _sample_oid = _reported_doc.get("sample_oid")
            _report_oid = _reported_doc.get("report_oid")
            _annotation_text_oid = _reported_doc.get("annotation_text_oid")
            _report_id = _reported_doc.get("report_id")
            _sample = store.sample_handler.get_sample_by_oid(_sample_oid)
            _sample_name = (
                _reported_doc.get("sample_name") or _sample.get("name") if _sample else None
            )
            _report_num = next(
                (
                    rpt.get("report_num")
                    for rpt in (_sample.get("reports") or [])
                    if rpt.get("_id") == _report_oid
                ),
                None,
            )

            if _sample_oid:
                if _sample_oid not in _sample_oids:
                    _sample_oids[_sample_oid] = {
                        "sample_name": _sample_name if _sample_name else "UNKNOWN_SAMPLE",
                        "report_oids": {},
                    }
                if _report_oid and _report_id:
                    if _report_oid not in _sample_oids.get(_sample_oid, {}).get("report_oids", {}):
                        _sample_oids[_sample_oid]["report_oids"][_report_id] = _report_num

            if include_annotation_text and _annotation_text_oid:
                _annotation_text_oids_associated_with_variants.add(_annotation_text_oid)
                _doc["text"] = store.annotation_handler.get_annotation_text_by_oid(
                    _annotation_text_oid
                )

        _doc["reported_docs"] = _reported_docs
        _doc["samples"] = _sample_oids

        if _doc.get("_id") not in _annotation_text_oids_associated_with_variants:
            sample_tagged_docs.append(_doc)

    return render_template(
        "search_tiered_variants.html",
        docs=sample_tagged_docs,
        search_str=search_str,
        search_mode=search_mode,
        include_annotation_text=include_annotation_text,
        tier_stats=tier_stats,
        assays=assays,
        form=form,
    )
