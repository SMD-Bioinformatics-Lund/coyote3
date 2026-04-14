"""Comment helpers for DNA service workflows."""

from __future__ import annotations


def add_variant_comment(
    service,
    *,
    form_data: dict,
    target_id: str,
    get_variant_nomenclature_fn,
    create_comment_doc_fn,
) -> str:
    """Create a resource comment and return its response resource label."""
    nomenclature, variant = get_variant_nomenclature_fn(form_data)
    doc = create_comment_doc_fn(form_data, nomenclature=nomenclature, variant=variant)
    comment_scope = form_data.get("global")
    if comment_scope == "global":
        service.annotation_handler.add_anno_comment(doc)
    if nomenclature == "f":
        if comment_scope != "global":
            service.fusion_handler.add_fusion_comment(target_id, doc)
        return "fusion_comment"
    if nomenclature == "t":
        if comment_scope != "global":
            service.translocation_handler.add_transloc_comment(target_id, doc)
        return "translocation_comment"
    if nomenclature == "cn":
        if comment_scope != "global":
            service.copy_number_variant_handler.add_cnv_comment(target_id, doc)
        return "cnv_comment"
    if comment_scope != "global":
        service.variant_handler.add_var_comment(target_id, doc)
    return "variant_comment"
