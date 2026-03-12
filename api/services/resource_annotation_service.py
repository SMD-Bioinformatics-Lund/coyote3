"""Cross-resource annotation/comment workflow service."""

from __future__ import annotations

from typing import Any

from api.repositories.dna_repository import DnaRouteRepository


class ResourceAnnotationService:
    """Provide resource annotation workflows.
    """
    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or DnaRouteRepository()

    @staticmethod
    def mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict[str, Any]:
        """Handle mutation payload.

        Args:
            sample_id (str): Value for ``sample_id``.
            resource (str): Value for ``resource``.
            resource_id (str): Value for ``resource_id``.
            action (str): Value for ``action``.

        Returns:
            dict[str, Any]: The function result.
        """
        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "resource": resource,
            "resource_id": str(resource_id),
            "action": action,
            "meta": {"status": "updated"},
        }

    def create_annotation(
        self,
        *,
        form_data: dict,
        target_id: str,
        get_variant_nomenclature_fn,
        create_comment_doc_fn,
    ) -> str:
        """Create annotation.

        Args:
            form_data (dict): Value for ``form_data``.
            target_id (str): Value for ``target_id``.
            get_variant_nomenclature_fn: Value for ``get_variant_nomenclature_fn``.
            create_comment_doc_fn: Value for ``create_comment_doc_fn``.

        Returns:
            str: The function result.
        """
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        doc = create_comment_doc_fn(form_data, nomenclature=nomenclature, variant=variant)
        comment_scope = form_data.get("global")
        if comment_scope == "global":
            self.repository.annotation_handler.add_anno_comment(doc)
        if nomenclature == "f":
            if comment_scope != "global":
                self.repository.fusion_handler.add_fusion_comment(target_id, doc)
            return "fusion_comment"
        if nomenclature == "t":
            if comment_scope != "global":
                self.repository.transloc_handler.add_transloc_comment(target_id, doc)
            return "translocation_comment"
        if nomenclature == "cn":
            if comment_scope != "global":
                self.repository.cnv_handler.add_cnv_comment(target_id, doc)
            return "cnv_comment"
        if comment_scope != "global":
            self.repository.variant_handler.add_var_comment(target_id, doc)
        return "variant_comment"


__all__ = ["ResourceAnnotationService"]
