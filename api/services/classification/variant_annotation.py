"""Cross-resource annotation/comment workflow service."""

from __future__ import annotations

from typing import Any


class ResourceAnnotationService:
    """Provide resource annotation workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceAnnotationService":
        """Build the service from the shared store."""
        return cls(
            annotation_handler=store.annotation_handler,
            fusion_handler=store.fusion_handler,
            translocation_handler=store.translocation_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            variant_handler=store.variant_handler,
        )

    def __init__(
        self,
        *,
        annotation_handler: Any,
        fusion_handler: Any,
        translocation_handler: Any,
        copy_number_variant_handler: Any,
        variant_handler: Any,
    ) -> None:
        """Create the service with explicit injectable handlers."""
        self.annotation_handler = annotation_handler
        self.fusion_handler = fusion_handler
        self.translocation_handler = translocation_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.variant_handler = variant_handler

    def create_annotation(
        self,
        *,
        form_data: dict,
        target_id: str,
        get_variant_nomenclature_fn,
        create_comment_doc_fn,
    ) -> str:
        """Create and persist an annotation for a classified resource.

        Args:
            form_data: Submitted annotation form payload.
            target_id: Resource identifier to annotate.
            get_variant_nomenclature_fn: Helper that resolves nomenclature and variant label.
            create_comment_doc_fn: Helper that builds the annotation document.

        Returns:
            str: Annotation event label for downstream callers.
        """
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        doc = create_comment_doc_fn(form_data, nomenclature=nomenclature, variant=variant)
        comment_scope = form_data.get("global")
        if comment_scope == "global":
            self.annotation_handler.add_anno_comment(doc)
        if nomenclature == "f":
            if comment_scope != "global":
                self.fusion_handler.add_fusion_comment(target_id, doc)
            return "fusion_comment"
        if nomenclature == "t":
            if comment_scope != "global":
                self.translocation_handler.add_transloc_comment(target_id, doc)
            return "translocation_comment"
        if nomenclature == "cn":
            if comment_scope != "global":
                self.copy_number_variant_handler.add_cnv_comment(target_id, doc)
            return "cnv_comment"
        if comment_scope != "global":
            self.variant_handler.add_var_comment(target_id, doc)
        return "variant_comment"


__all__ = ["ResourceAnnotationService"]
