"""DNA small-variant action routes and shared helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Response, flash, redirect, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


def headers() -> dict[str, str]:
    """Handle headers.

    Returns:
        dict[str, str]: The function result.
    """
    return forward_headers()


def call_api(sample_id: str, log_message: str, api_call: Callable[[], Any]) -> bool:
    """Handle call api.

    Args:
        sample_id (str): Value for ``sample_id``.
        log_message (str): Value for ``log_message``.
        api_call (Callable[[], Any]): Value for ``api_call``.

    Returns:
        bool: The function result.
    """
    try:
        api_call()
        return True
    except ApiRequestError as exc:
        app.logger.error("%s for sample %s: %s", log_message, sample_id, exc)
        return False


def resolve_target_id(*keys: str) -> str:
    """Handle resolve target id.

    Args:
        *keys (str): Additional positional values for ``keys``.

    Returns:
        str: The function result.
    """
    for key in keys:
        value = request.view_args.get(key)
        if value:
            return value
    return ""


def derive_nomenclature(form_data: dict[str, Any]) -> str:
    """Handle derive nomenclature.

    Args:
        form_data (dict[str, Any]): Value for ``form_data``.

    Returns:
        str: The function result.
    """
    if form_data.get("fusionpoints"):
        return "f"
    if form_data.get("translocpoints"):
        return "t"
    if form_data.get("cnvvar"):
        return "cn"
    return "p"


def derive_resource_type(form_data: dict[str, Any]) -> str:
    """Handle derive resource type.

    Args:
        form_data (dict[str, Any]): Value for ``form_data``.

    Returns:
        str: The function result.
    """
    nomenclature = derive_nomenclature(form_data)
    if nomenclature == "f":
        return "fusion"
    if nomenclature == "t":
        return "translocation"
    if nomenclature == "cn":
        return "cnv"
    return "small_variant"


def redirect_target(sample_id: str, target_id: str, nomenclature: str) -> Response:
    """Handle redirect target.

    Args:
        sample_id (str): Value for ``sample_id``.
        target_id (str): Value for ``target_id``.
        nomenclature (str): Value for ``nomenclature``.

    Returns:
        Response: The function result.
    """
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=target_id))
    if nomenclature == "t":
        return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=target_id))
    if nomenclature == "cn":
        return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=target_id))
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=target_id))


def bulk_toggle(
    sample_id: str,
    enabled: str | None,
    action: str | None,
    resource_ids: list[str],
    operation_label: str,
    endpoint: str,
) -> None:
    """Handle bulk toggle.

    Args:
        sample_id (str): Value for ``sample_id``.
        enabled (str | None): Value for ``enabled``.
        action (str | None): Value for ``action``.
        resource_ids (list[str]): Value for ``resource_ids``.
        operation_label (str): Value for ``operation_label``.
        endpoint (str): Value for ``endpoint``.

    Returns:
        None.
    """
    if not enabled or action not in {"apply", "remove"}:
        return

    apply = action == "apply"
    verb = "mark" if apply else "unmark"
    call_api(
        sample_id,
        f"Failed to bulk {verb} small variants {operation_label} via API",
        lambda: get_web_api_client().patch_json(
            endpoint,
            headers=headers(),
            json_body={
                "apply": apply,
                "resource_ids": resource_ids,
                "resource_type": "small_variant",
            },
        ),
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@login_required
def unmark_false_variant(sample_id: str, var_id: str) -> Response:
    """Handle unmark false variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to unmark variant false-positive via API",
        lambda: get_web_api_client().delete_json(
            api_endpoints.dna_sample(
                sample_id, "small_variants", var_id, "flags", "false-positive"
            ),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@login_required
def mark_false_variant(sample_id: str, var_id: str) -> Response:
    """Handle mark false variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to mark variant false-positive via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(
                sample_id, "small_variants", var_id, "flags", "false-positive"
            ),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"])
@login_required
def unmark_interesting_variant(sample_id: str, var_id: str) -> Response:
    """Handle unmark interesting variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to unmark variant interesting via API",
        lambda: get_web_api_client().delete_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id, "flags", "interesting"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"])
@login_required
def mark_interesting_variant(sample_id: str, var_id: str) -> Response:
    """Handle mark interesting variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to mark variant interesting via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id, "flags", "interesting"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/relevant", methods=["POST"])
@login_required
def unmark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    """Handle unmark irrelevant variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to unmark variant irrelevant via API",
        lambda: get_web_api_client().delete_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id, "flags", "irrelevant"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"])
@login_required
def mark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    """Handle mark irrelevant variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to mark variant irrelevant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id, "flags", "irrelevant"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"])
@login_required
def add_variant_to_blacklist(sample_id: str, var_id: str) -> Response:
    """Handle add variant to blacklist.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    call_api(
        sample_id,
        "Failed to blacklist variant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id, "blacklist-entries"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/add_variant_comment",
    methods=["POST"],
    endpoint="add_variant_comment",
)
@dna_bp.route(
    "/<string:sample_id>/cnv/<string:cnv_id>/add_cnv_comment",
    methods=["POST"],
    endpoint="add_cnv_comment",
)
@dna_bp.route(
    "/<string:sample_id>/fusion/<string:fus_id>/add_fusion_comment",
    methods=["POST"],
    endpoint="add_fusion_comment",
)
@dna_bp.route(
    "/<string:sample_id>/translocation/<string:transloc_id>/add_translocation_comment",
    methods=["POST"],
    endpoint="add_translocation_comment",
)
@login_required
def add_var_comment(sample_id: str, id: str | None = None, **kwargs: Any) -> Response:
    """Handle add var comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        id (str | None): Value for ``id``.
        **kwargs (Any): Additional keyword values for ``kwargs``.

    Returns:
        Response: The function result.
    """
    _ = kwargs
    target_id = id or resolve_target_id("var_id", "cnv_id", "fus_id", "transloc_id")

    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)
    comment_scope = form_data.get("global")

    call_ok = call_api(
        sample_id,
        "Failed to add comment via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "annotations"),
            headers=headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    if call_ok and comment_scope == "global":
        flash("Global comment added", "green")

    return redirect_target(sample_id, target_id, nomenclature)


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/hide_variant_comment", methods=["POST"])
@login_required
def hide_variant_comment(sample_id: str, var_id: str) -> Response:
    """Handle hide variant comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    call_api(
        sample_id,
        "Failed to hide variant comment via API",
        lambda: get_web_api_client().patch_json(
            api_endpoints.dna_sample(
                sample_id, "small_variants", var_id, "comments", comment_id, "hidden"
            ),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unhide_variant_comment", methods=["POST"])
@login_required
def unhide_variant_comment(sample_id: str, var_id: str) -> Response:
    """Handle unhide variant comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str): Value for ``var_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    call_api(
        sample_id,
        "Failed to unhide variant comment via API",
        lambda: get_web_api_client().delete_json(
            api_endpoints.dna_sample(
                sample_id, "small_variants", var_id, "comments", comment_id, "hidden"
            ),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_small_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/classify",
    methods=["POST"],
    endpoint="classify_small_variant",
)
@dna_bp.route(
    "/<string:sample_id>/fus/<string:fus_id>/classify", methods=["POST"], endpoint="classify_fusion"
)
@login_required
def classify_small_variant(
    sample_id: str, var_id: str | None = None, fus_id: str | None = None
) -> Response:
    """Handle classify small variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str | None): Value for ``var_id``.
        fus_id (str | None): Value for ``fus_id``.

    Returns:
        Response: The function result.
    """
    target_id = var_id or fus_id or resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)
    resource_type = derive_resource_type(form_data)
    call_api(
        sample_id,
        "Failed to classify variant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "classifications"),
            headers=headers(),
            json_body={"id": target_id, "resource_type": resource_type, "form_data": form_data},
        ),
    )
    return redirect_target(sample_id, target_id, nomenclature)


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_small_variant",
)
@dna_bp.route(
    "/<string:sample_id>/fus/<string:fus_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_fusion",
)
@login_required
def remove_classified_small_variant(
    sample_id: str, var_id: str | None = None, fus_id: str | None = None
) -> Response:
    """Remove classified small variant.

    Args:
        sample_id (str): Value for ``sample_id``.
        var_id (str | None): Value for ``var_id``.
        fus_id (str | None): Value for ``fus_id``.

    Returns:
        Response: The function result.
    """
    target_id = var_id or fus_id or resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)
    resource_type = derive_resource_type(form_data)

    call_api(
        sample_id,
        "Failed to remove classification via API",
        lambda: get_web_api_client().delete_json(
            api_endpoints.dna_sample(sample_id, "classifications"),
            headers=headers(),
            json_body={"id": target_id, "resource_type": resource_type, "form_data": form_data},
        ),
    )
    return redirect_target(sample_id, target_id, nomenclature)


@dna_bp.route("/<sample_id>/multi_class", methods=["POST"], endpoint="classify_multi_small_variant")
@login_required
def classify_multi_small_variant(sample_id: str) -> Response:
    """Handle classify multi small variant.

    Args:
        sample_id (str): Value for ``sample_id``.

    Returns:
        Response: The function result.
    """
    action = request.form.get("action")
    variants_to_modify = request.form.getlist("selected_object_id")
    assay_group = request.form.get("assay_group")
    subpanel = request.form.get("subpanel")
    tier = request.form.get("tier")
    irrelevant = request.form.get("irrelevant")
    false_positive = request.form.get("false_positive")

    if tier and action in {"apply", "remove"}:
        call_api(
            sample_id,
            "Failed to bulk update small-variant tier via API",
            lambda: get_web_api_client().patch_json(
                api_endpoints.dna_sample(sample_id, "small_variants", "tier"),
                headers=headers(),
                json_body={
                    "apply": action == "apply",
                    "resource_ids": variants_to_modify,
                    "resource_type": "small_variant",
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "tier": 3,
                },
            ),
        )

    bulk_toggle(
        sample_id=sample_id,
        enabled=false_positive,
        action=action,
        resource_ids=variants_to_modify,
        operation_label="false-positive",
        endpoint=api_endpoints.dna_sample(sample_id, "small_variants", "flags", "false-positive"),
    )
    bulk_toggle(
        sample_id=sample_id,
        enabled=irrelevant,
        action=action,
        resource_ids=variants_to_modify,
        operation_label="irrelevant",
        endpoint=api_endpoints.dna_sample(sample_id, "small_variants", "flags", "irrelevant"),
    )

    return redirect(url_for("dna_bp.list_small_variants", sample_id=sample_id))
