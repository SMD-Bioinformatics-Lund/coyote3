"""Cross-resource annotation/comment workflow service."""

from __future__ import annotations

from typing import Any

from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.finding_access import require_sample_finding
from coyote3.domain.annotation_scope import annotation_namespace


class ResourceAnnotationService:
    """Provide resource annotation workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceAnnotationService":
        """Build the service from the runtime store."""
        return cls(
            annotation_repository=store.annotation_repository,
            fusion_repository=store.fusion_repository,
            translocation_repository=store.translocation_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            variant_repository=store.variant_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
        )

    def __init__(
        self,
        *,
        annotation_repository: Any,
        fusion_repository: Any,
        translocation_repository: Any,
        copy_number_variant_repository: Any,
        variant_repository: Any,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
    ) -> None:
        """Create the service with explicit injectable repositories."""
        self.annotation_repository = annotation_repository
        self.fusion_repository = fusion_repository
        self.translocation_repository = translocation_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.variant_repository = variant_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository

    def require_resource_for_sample(
        self,
        *,
        sample: dict[str, Any],
        nomenclature: str,
        target_id: str,
    ) -> dict[str, Any]:
        """Require that the annotated finding belongs to the authorized sample."""
        if nomenclature == "f":
            return require_sample_finding(sample, target_id, self.fusion_repository.get_fusion)
        if nomenclature == "t":
            return require_sample_finding(
                sample, target_id, self.translocation_repository.get_transloc
            )
        if nomenclature == "cn":
            return require_sample_finding(
                sample, target_id, self.copy_number_variant_repository.get_cnv
            )
        return require_sample_finding(sample, target_id, self.variant_repository.get_variant)

    def create_annotation(
        self,
        *,
        form_data: dict,
        target_id: str,
        get_variant_nomenclature_fn,
        create_comment_doc_fn,
        sample: dict[str, Any],
    ) -> str:
        """Create and persist an annotation for a classified resource.

        Args:
            form_data: Submitted annotation form payload.
            target_id: Resource identifier to annotate.
            get_variant_nomenclature_fn: Helper that resolves nomenclature and variant label.
            create_comment_doc_fn: Helper that builds the annotation document.
            sample: Authorized sample whose identity must own the target finding.

        Returns:
            str: Annotation event label for downstream callers.
        """
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        self.require_resource_for_sample(
            sample=sample,
            nomenclature=nomenclature,
            target_id=target_id,
        )
        doc = create_comment_doc_fn(form_data, nomenclature=nomenclature, variant=variant)
        comment_scope = form_data.get("global")
        if comment_scope == "global":
            configuration = get_formatted_assay_config(
                sample,
                assay_configuration_repository=self.assay_configuration_repository,
                assay_panel_repository=self.assay_panel_repository,
            )
            context = configuration["aspc_resolution"]["context"]
            doc["asp_group"] = context["group_id"]
            doc["asp_id"] = context["assay_id"]
            doc["diagnosis_id"] = context["diagnosis_id"]
            doc["namespace"] = annotation_namespace(sample["environment"])
            doc["source_sample_id"] = str(sample["_id"])
            doc["source_finding_id"] = str(target_id)
            self.annotation_repository.add_anno_comment(doc)
        if nomenclature == "f":
            if comment_scope != "global":
                self.fusion_repository.add_fusion_comment(target_id, doc)
            return "fusion_comment"
        if nomenclature == "t":
            if comment_scope != "global":
                self.translocation_repository.add_transloc_comment(target_id, doc)
            return "translocation_comment"
        if nomenclature == "cn":
            if comment_scope != "global":
                self.copy_number_variant_repository.add_cnv_comment(target_id, doc)
            return "cnv_comment"
        if comment_scope != "global":
            self.variant_repository.add_var_comment(target_id, doc)
        return "variant_comment"


__all__ = ["ResourceAnnotationService"]
