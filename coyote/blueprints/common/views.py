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
            f"Unrecognized omics type {sample["name"]}! Unable to redirect to the sample page"
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
            f"Unrecognized omics type {sample["name"]}! Unable to redirect to the sample page"
        )
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


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
@require("view_tiered_variants", min_role="user", min_level=9)
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

    docs_found = store.annotation_handler.find_variants_by_search_string(
        search_str=search_str,
        search_mode=search_mode,
        include_annotation_text=include_annotation_text,
        assays=assays,
        limit=limit_entries,
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

    # Enrich docs with sample details, variant details, report details
    # docs = util.bpcommon.enrich_reported_variant_docs(deepcopy(sample_tagged_docs))

    return render_template(
        "search_tiered_variants.html",
        docs=sample_tagged_docs,
        search_str=search_str,
        search_mode=search_mode,
        include_annotation_text=include_annotation_text,
        form=form,
    )
