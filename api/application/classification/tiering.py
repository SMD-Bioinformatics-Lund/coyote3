"""Cross-resource classification service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.domain.common.errors import api_error


class ResourceClassificationService:
    """Own cross-resource classification and tiering workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceClassificationService":
        """Build the service from the runtime store."""
        return cls(
            annotation_repository=store.annotation_repository,
            variant_repository=store.variant_repository,
            oncokb_repository=store.oncokb_repository,
            fusion_repository=store.fusion_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            translocation_repository=store.translocation_repository,
            assay_configuration_repository=store.assay_configuration_repository,
        )

    def __init__(
        self,
        *,
        annotation_repository: Any,
        variant_repository: Any,
        oncokb_repository: Any,
        fusion_repository: Any,
        copy_number_variant_repository: Any,
        translocation_repository: Any,
        assay_configuration_repository: Any,
    ) -> None:
        """Build the classification service with explicit persistence dependencies."""
        self.annotation_repository = annotation_repository
        self.variant_repository = variant_repository
        self.oncokb_repository = oncokb_repository
        self.fusion_repository = fusion_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.translocation_repository = translocation_repository
        self.assay_configuration_repository = assay_configuration_repository

    def classification_context(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Resolve immutable assay context for a finding classification."""
        assay = str(sample.get("assay") or "").strip()
        profile = str(sample.get("profile") or "production").strip()
        subpanel = str(sample.get("subpanel_id") or sample.get("subpanel") or "base").strip()
        aspc = self.assay_configuration_repository.get_aspc_no_meta(assay, profile, subpanel)
        if not isinstance(aspc, dict):
            raise api_error(
                422,
                "The sample has no active assay configuration; classification context cannot be resolved",
            )
        return {
            "assay_group": str(aspc.get("asp_group") or "").strip(),
            "subpanel": str(aspc.get("subpanel_id") or subpanel).strip(),
        }

    @staticmethod
    def _consequence_list(value: object) -> list[str]:
        """Normalize selected_CSQ consequence values into list form."""
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
        value = str(resource_type or "small_variant").strip().lower().replace("-", "_")
        aliases = {
            "variant": "small_variant",
            "snv": "small_variant",
            "small_variants": "small_variant",
            "fusion": "fusion",
            "cnv": "cnv",
            "transloc": "translocation",
            "translocation": "translocation",
        }
        return aliases.get(value, value)

    def _load_resource_identity(
        self,
        *,
        sample: dict,
        resource_type: str,
        resource_id: str,
        classification_context: dict[str, Any],
        create_annotation_text_fn,
        create_automatic_text: bool,
    ) -> dict[str, Any] | None:
        """Load the identity payload needed for resource classification.

        Args:
            sample: Sample payload containing ownership context.
            resource_type: Resource type to classify.
            resource_id: Resource identifier to load.
            classification_context: Server-resolved ASPC context.
            create_annotation_text_fn: Helper used to build default annotation text.
            create_automatic_text: Whether to generate the approved Tier 3 SNV narrative.

        Returns:
            dict[str, Any] | None: Classification identity payload, when the resource exists.
        """
        normalized_type = self.normalize_resource_type(resource_type)
        assay_group = classification_context.get("assay_group")
        base_context = dict(classification_context)
        if normalized_type == "small_variant":
            var = self.variant_repository.get_variant(str(resource_id))
            if not var or str(var.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None

            selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
            transcript = selected_csq.get("Feature")
            gene = selected_csq.get("SYMBOL")
            hgvs_p = selected_csq.get("HGVSp")
            hgvs_c = selected_csq.get("HGVSc")
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = self._consequence_list(selected_csq.get("Consequence"))
            text = None
            if create_automatic_text:
                gene_oncokb = self.oncokb_repository.get_oncokb_gene(gene)
                text = create_annotation_text_fn(
                    gene, consequence, assay_group, gene_oncokb=gene_oncokb
                )

            nomenclature = "p"
            if hgvs_p not in {"", None}:
                variant = hgvs_p
            elif hgvs_c not in {"", None}:
                variant = hgvs_c
                nomenclature = "c"
            else:
                variant = hgvs_g
                nomenclature = "g"

            return {
                "variant": variant,
                "nomenclature": nomenclature,
                "text": text,
                "variant_data": {
                    **base_context,
                    "gene": gene,
                    "transcript": transcript,
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
                "text": None,
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
            genes = cnv.get("genes", [])
            gene_label = None
            if genes:
                first_gene = genes[0]
                gene_label = (
                    first_gene.get("gene") if isinstance(first_gene, dict) else str(first_gene)
                )
            return {
                "variant": f"{cnv.get('chr')}:{cnv.get('start')}-{cnv.get('end')}",
                "nomenclature": "cn",
                "text": None,
                "variant_data": {
                    **base_context,
                    "gene": gene_label,
                },
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
            gene_label = None
            if annotations:
                first_annotation = annotations[0]
                gene_names = str(first_annotation.get("Gene_Name", "")).split("&")
                gene_label = "-".join([gene for gene in gene_names if gene])
            return {
                "variant": f"{transloc.get('CHROM')}:{transloc.get('POS')}^{transloc.get('ALT')}",
                "nomenclature": "t",
                "text": None,
                "variant_data": {
                    **base_context,
                    "gene": gene_label,
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
        create_annotation_text_fn,
        create_classified_variant_doc_fn,
    ) -> None:
        """Apply or remove tier classifications in bulk.

        Args:
            sample: Sample payload containing ownership context.
            resource_type: Resource type to classify.
            resource_ids: Resource identifiers to update.
            apply: Whether to add or remove the classification.
            class_num: Target tier/class number.
            create_annotation_text_fn: Helper used to build default annotation text.
            create_classified_variant_doc_fn: Helper used to build classification documents.
        """
        bulk_docs: list[dict[str, Any]] = []
        classification_context = self.classification_context(sample)
        normalized_type = self.normalize_resource_type(resource_type)
        create_automatic_text = normalized_type == "small_variant" and class_num == 3
        for resource_id in resource_ids:
            identity = self._load_resource_identity(
                sample=sample,
                resource_type=resource_type,
                resource_id=str(resource_id),
                classification_context=classification_context,
                create_annotation_text_fn=create_annotation_text_fn,
                create_automatic_text=create_automatic_text,
            )
            if not identity:
                continue

            if not apply:
                self.annotation_repository.delete_classified_variant(
                    variant=identity["variant"],
                    nomenclature=identity["nomenclature"],
                    variant_data=identity["variant_data"],
                    class_num=class_num,
                    annotation_text=identity["text"] if create_automatic_text else None,
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
            if create_automatic_text:
                bulk_docs.append(
                    deepcopy(
                        create_classified_variant_doc_fn(
                            variant=identity["variant"],
                            nomenclature=identity["nomenclature"],
                            class_num=class_num,
                            variant_data=identity["variant_data"],
                            text=identity["text"],
                        )
                    )
                )

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
        """Remove a classification document for a resource."""
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        self.annotation_repository.delete_classified_variant(variant, nomenclature, form_data)


__all__ = ["ResourceClassificationService"]
