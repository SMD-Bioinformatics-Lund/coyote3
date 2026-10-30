"""Cross-resource classification service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from coyote3.application.classification.bulk_annotation_rules import (
    bulk_annotation_group_options,
    render_bulk_annotation,
)
from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.finding_access import require_sample_finding
from coyote3.application.reporting.clinical_rules.service import ClinicalRuleService
from coyote3.contracts.schemas.clinical_rules import BulkAnnotationPreviewRequest
from coyote3.domain.annotation_identity import primary_small_variant_identity
from coyote3.domain.annotation_scope import annotation_namespace
from coyote3.domain.common.errors import api_error
from coyote3.domain.dna.structural_identity import translocation_annotation_identity
from coyote3.domain.finding_types import normalize_finding_kind


class ResourceClassificationService:
    """Own cross-resource classification and tiering workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceClassificationService":
        """Build the service from the runtime store."""
        return cls(
            annotation_repository=store.annotation_repository,
            variant_repository=store.variant_repository,
            fusion_repository=store.fusion_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            translocation_repository=store.translocation_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            assay_group_repository=store.assay_group_repository,
            oncokb_repository=store.oncokb_repository,
            clinical_rule_service=ClinicalRuleService.from_store(store),
        )

    def __init__(
        self,
        *,
        annotation_repository: Any,
        variant_repository: Any,
        fusion_repository: Any,
        copy_number_variant_repository: Any,
        translocation_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: Any,
        assay_group_repository: Any,
        oncokb_repository: Any,
        clinical_rule_service: ClinicalRuleService | None = None,
    ) -> None:
        """Build the classification service with explicit persistence dependencies."""
        self.annotation_repository = annotation_repository
        self.variant_repository = variant_repository
        self.fusion_repository = fusion_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.translocation_repository = translocation_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_group_repository = assay_group_repository
        self.oncokb_repository = oncokb_repository
        self.clinical_rule_service = clinical_rule_service

    def classification_context(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Resolve immutable assay context for a finding classification."""
        aspc = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )
        if not isinstance(aspc, dict):
            raise api_error(
                422,
                "The sample has no active assay configuration; classification context cannot be resolved",
            )
        return {
            "asp_group": str(aspc.get("asp_group") or "").strip(),
            "asp_id": sample["asp_id"],
            "namespace": annotation_namespace(sample["environment"]),
            "diagnosis_id": str(sample.get("diagnosis_id") or "base").strip(),
            "reporting_language": (aspc.get("reporting") or {}).get("language", "sv"),
            "configuration": aspc,
        }

    @staticmethod
    def _consequence_list(value: object) -> list[str]:
        """Normalize a selected transcript's consequence value."""
        if isinstance(value, str):
            return [part.strip() for part in value.split("&") if part.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        if value in {None, ""}:
            return []
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def normalize_resource_type(resource_type: str | None) -> str:
        """Normalize incoming resource-type aliases.

        Args:
            resource_type: Raw resource type from the request.

        Returns:
            str: Canonical resource type identifier.
        """
        return normalize_finding_kind(resource_type)

    def require_resource_for_sample(
        self,
        *,
        sample: dict[str, Any],
        resource_type: str,
        resource_id: str,
    ) -> dict[str, Any]:
        """Require that the target finding belongs to the authorized sample."""
        normalized_type = self.normalize_resource_type(resource_type)
        if normalized_type == "small_variant":
            return require_sample_finding(sample, resource_id, self.variant_repository.get_variant)
        if normalized_type == "fusion":
            return require_sample_finding(sample, resource_id, self.fusion_repository.get_fusion)
        if normalized_type == "cnv":
            return require_sample_finding(
                sample,
                resource_id,
                self.copy_number_variant_repository.get_cnv,
            )
        if normalized_type == "translocation":
            return require_sample_finding(
                sample,
                resource_id,
                self.translocation_repository.get_transloc,
            )
        raise api_error(400, f"Unsupported resource_type: {resource_type}")

    def _load_resource_identity(
        self,
        *,
        sample: dict,
        resource_type: str,
        resource_id: str,
        classification_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Load the identity payload needed for resource classification.

        Args:
            sample: Sample payload containing ownership context.
            resource_type: Resource type to classify.
            resource_id: Resource identifier to load.
            classification_context: Server-resolved ASPC context.
        Returns:
            dict[str, Any] | None: Classification identity payload, when the resource exists.
        """
        normalized_type = self.normalize_resource_type(resource_type)
        base_context = {
            key: classification_context[key]
            for key in ("asp_group", "asp_id", "diagnosis_id", "namespace")
        }
        base_context.update(source_sample_id=str(sample["_id"]), source_finding_id=str(resource_id))
        if normalized_type == "small_variant":
            var = self.variant_repository.get_variant(str(resource_id))
            if not var or str(var.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None

            selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
            transcript = selected_csq.get("Feature")
            gene = selected_csq.get("SYMBOL")
            hgvs_p = selected_csq.get("HGVSp")
            hgvs_c = selected_csq.get("HGVSc")
            nomenclature, variant = primary_small_variant_identity(var)

            return {
                "variant": variant,
                "nomenclature": nomenclature,
                "automatic_text_context": {
                    "gene": gene,
                    "consequence": selected_csq.get("Consequence"),
                    "variant_type": selected_csq.get("VARIANT_CLASS"),
                },
                "variant_data": {
                    **base_context,
                    "gene": gene,
                    "transcript": transcript,
                    "hgvsp": hgvs_p,
                    "hgvsc": hgvs_c,
                    "genomic": var.get("simple_id"),
                    "genomic_hash": var.get("simple_id_hash"),
                },
            }

        if normalized_type == "fusion":
            fusion = self.fusion_repository.get_fusion(str(resource_id))
            if not fusion or str(fusion.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None
            selected_call = self.fusion_repository.get_selected_fusioncall(fusion)
            if not selected_call:
                return None
            gene1 = fusion.get("gene1")
            gene2 = fusion.get("gene2")
            return {
                "variant": f"{selected_call.get('breakpoint1', '')}^{selected_call.get('breakpoint2', '')}",
                "nomenclature": "f",
                "variant_data": {
                    **base_context,
                    "gene1": gene1,
                    "gene2": gene2,
                },
            }

        if normalized_type == "cnv":
            cnv = self.copy_number_variant_repository.get_cnv(str(resource_id))
            if not cnv or str(cnv.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None
            return {
                "variant": f"{cnv.get('chr')}:{cnv.get('start')}-{cnv.get('end')}",
                "nomenclature": "cn",
                "variant_data": base_context,
            }

        if normalized_type == "translocation":
            transloc = self.translocation_repository.get_transloc(str(resource_id))
            if not transloc or str(transloc.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None
            info = transloc.get("INFO") or {}
            if isinstance(info, list):
                info = next((item for item in info if isinstance(item, dict)), {})
            mane_annotation = info.get("MANE_ANN")
            annotations = (
                [mane_annotation] if isinstance(mane_annotation, dict) else info.get("ANN", [])
            )
            gene1 = None
            gene2 = None
            if annotations:
                first_annotation = annotations[0]
                gene_names = str(first_annotation.get("Gene_Name", "")).split("&")
                genes = [gene for gene in gene_names if gene]
                gene1 = genes[0] if genes else None
                gene2 = genes[1] if len(genes) > 1 else None
            return {
                "variant": translocation_annotation_identity(transloc),
                "nomenclature": "t",
                "variant_data": {
                    **base_context,
                    "gene1": gene1,
                    "gene2": gene2,
                },
            }

        raise api_error(400, f"Unsupported resource_type: {resource_type}")

    def set_tier_bulk(
        self,
        *,
        sample: dict,
        resource_type: str,
        resource_ids: list[str],
        apply: bool,
        class_num: int,
        create_classified_variant_doc_fn,
        include_automatic_text: bool = False,
        deactivation_scope: str = "diagnosis",
        preview_only: bool = False,
        annotation_rule_hash: str | None = None,
    ) -> list[dict[str, Any]] | None:
        """Assign tiers or deactivate matching annotations in bulk.

        Args:
            sample: Sample payload containing ownership context.
            resource_type: Resource type to classify.
            resource_ids: Resource identifiers to update.
            apply: Whether to add or remove the classification.
            class_num: Target tier/class number.
            create_classified_variant_doc_fn: Helper used to build classification documents.
            include_automatic_text: Whether to add supported application-generated text.
            deactivation_scope: Diagnosis limits deactivation to the current assay/diagnosis/tier;
                group retires all finding annotations across assays and diagnoses in the group.
            preview_only: Return generated text per finding without any writes.
            annotation_rule_hash: Optional previewed release hash; reject a changed release.

        Returns:
            Preview rows when requested; None after a persisted action.
        """
        if deactivation_scope not in {"diagnosis", "group"} or (
            apply and deactivation_scope == "group"
        ):
            raise api_error(422, "Invalid deactivation scope")
        bulk_docs: list[dict[str, Any]] = []
        classification_context = self.classification_context(sample)
        normalized_type = self.normalize_resource_type(resource_type)
        release = None
        groups = []
        oncokb_genes: dict[str, dict | None] = {}
        previews = []
        if preview_only and not (apply and include_automatic_text):
            raise api_error(422, "Annotation preview requires a bulk assignment with text")
        if include_automatic_text:
            if not apply or class_num not in {1, 2, 3} or normalized_type != "small_variant":
                raise api_error(
                    422, "Bulk annotation templates support small-variant Tier I–III assignments"
                )
            try:
                groups = bulk_annotation_group_options(self.assay_group_repository.list())
            except ValueError as error:
                raise api_error(422, "Biological group hierarchy is invalid", str(error)) from error
            try:
                if self.clinical_rule_service is not None:
                    release = self.clinical_rule_service.bulk_annotation_release(
                        aspc=classification_context["configuration"],
                        sample=sample,
                    )
            except ValueError as error:
                raise api_error(
                    422, "Automatic annotation requires valid published reporting rules", str(error)
                ) from error
            if release is None:
                raise api_error(
                    422,
                    "Publish bulk annotation rules for this assay and diagnosis first",
                )
            if annotation_rule_hash is not None and release.content_hash != annotation_rule_hash:
                raise api_error(
                    409, "Annotation rules changed after preview. Preview the text again."
                )
        for resource_id in resource_ids:
            identity = self._load_resource_identity(
                sample=sample,
                resource_type=resource_type,
                resource_id=str(resource_id),
                classification_context=classification_context,
            )
            if not identity:
                continue

            automatic_text = None
            rule_source = None
            if release is not None:
                text_context = identity["automatic_text_context"]
                gene = str(text_context.get("gene") or "").strip()
                if gene and self.oncokb_repository is not None and gene not in oncokb_genes:
                    oncokb_genes[gene] = self.oncokb_repository.get_oncokb_gene(gene)
                oncokb_gene = oncokb_genes.get(gene)
                description = oncokb_gene.get("description") if oncokb_gene else None
                try:
                    rendered = render_bulk_annotation(
                        release,
                        BulkAnnotationPreviewRequest(
                            tier=class_num,
                            asp_group=classification_context["asp_group"] or None,
                            gene=text_context.get("gene"),
                            consequence=self._consequence_list(text_context.get("consequence")),
                            hgvsc=identity["variant_data"].get("hgvsc"),
                            hgvsp=identity["variant_data"].get("hgvsp"),
                            transcript=identity["variant_data"].get("transcript"),
                            variant_type=text_context.get("variant_type"),
                            oncokb_gene_present=bool(oncokb_gene)
                            if gene and self.oncokb_repository is not None
                            else None,
                            oncokb_gene_description=description
                            if isinstance(description, str)
                            else None,
                        ),
                        diagnosis_id=classification_context["diagnosis_id"],
                        groups=groups,
                    )
                except ValueError as error:
                    raise api_error(
                        422, "Bulk annotation text could not be generated", str(error)
                    ) from error
                automatic_text = rendered.text
                if rendered.rule_id:
                    rule_source = {
                        "rule_set_id": release.rule_set_id,
                        "content_version": release.content_version,
                        "revision": release.revision,
                        "content_hash": release.content_hash,
                        "rule_id": rendered.rule_id,
                        "tier": class_num,
                    }
                previews.append(
                    {
                        "resource_id": str(resource_id),
                        "content_hash": release.content_hash,
                        "gene": text_context.get("gene"),
                        **rendered.model_dump(),
                    }
                )
            if preview_only:
                continue

            if not apply:
                self.annotation_repository.deactivate_classified_variant(
                    variant=identity["variant"],
                    nomenclature=identity["nomenclature"],
                    variant_data=identity["variant_data"],
                    class_num=class_num,
                    annotation_text=automatic_text,
                    group=deactivation_scope == "group",
                )
                continue

            bulk_docs.append(
                deepcopy(
                    create_classified_variant_doc_fn(
                        variant=identity["variant"],
                        nomenclature=identity["nomenclature"],
                        class_num=class_num,
                        variant_data=identity["variant_data"],
                    )
                )
            )
            if include_automatic_text and automatic_text:
                annotation = deepcopy(
                    create_classified_variant_doc_fn(
                        variant=identity["variant"],
                        nomenclature=identity["nomenclature"],
                        class_num=class_num,
                        variant_data=identity["variant_data"],
                        text=automatic_text,
                    )
                )
                annotation["rule_source"] = rule_source
                bulk_docs.append(annotation)
        if preview_only:
            return previews
        if bulk_docs:
            self.annotation_repository.insert_annotation_bulk(bulk_docs)

    def classify_resource(
        self,
        *,
        resource_type: str,
        form_data: dict,
        get_tier_classification_fn,
        get_variant_nomenclature_fn,
    ) -> None:
        """Create a classification document for a resource."""
        class_num = get_tier_classification_fn(form_data)
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        if class_num != 0:
            self.annotation_repository.insert_classified_variant(
                variant, nomenclature, class_num, form_data
            )

    def remove_resource(
        self,
        *,
        resource_type: str,
        form_data: dict,
        get_variant_nomenclature_fn,
    ) -> None:
        """Deactivate matching resource classifications while retaining their stored history."""
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        self.annotation_repository.deactivate_classified_variant(variant, nomenclature, form_data)


__all__ = ["ResourceClassificationService"]
