"""Cross-resource classification service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.http import api_error


class ResourceClassificationService:
    """Own cross-resource classification and tiering workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "ResourceClassificationService":
        """Build the service from the shared store."""
        return cls(
            annotation_handler=store.annotation_handler,
            variant_handler=store.variant_handler,
            oncokb_handler=store.oncokb_handler,
            fusion_handler=store.fusion_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            translocation_handler=store.translocation_handler,
        )

    def __init__(
        self,
        *,
        annotation_handler: Any,
        variant_handler: Any,
        oncokb_handler: Any,
        fusion_handler: Any,
        copy_number_variant_handler: Any,
        translocation_handler: Any,
    ) -> None:
        """Build the classification service with explicit persistence dependencies."""
        self.annotation_handler = annotation_handler
        self.variant_handler = variant_handler
        self.oncokb_handler = oncokb_handler
        self.fusion_handler = fusion_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.translocation_handler = translocation_handler

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
        assay_group: str | None,
        subpanel: str | None,
        create_annotation_text_fn,
    ) -> dict[str, Any] | None:
        """Load the identity payload needed for resource classification.

        Args:
            sample: Sample payload containing ownership context.
            resource_type: Resource type to classify.
            resource_id: Resource identifier to load.
            assay_group: Assay-group context for annotation text.
            subpanel: Optional subpanel context.
            create_annotation_text_fn: Helper used to build default annotation text.

        Returns:
            dict[str, Any] | None: Classification identity payload, when the resource exists.
        """
        normalized_type = self.normalize_resource_type(resource_type)
        if normalized_type == "small_variant":
            var = self.variant_handler.get_variant(str(resource_id))
            if not var or str(var.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None

            selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
            transcript = selected_csq.get("Feature")
            gene = selected_csq.get("SYMBOL")
            hgvs_p = selected_csq.get("HGVSp")
            hgvs_c = selected_csq.get("HGVSc")
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = self._consequence_list(selected_csq.get("Consequence"))
            gene_oncokb = self.oncokb_handler.get_oncokb_gene(gene)
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
                    "gene": gene,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "transcript": transcript,
                    "resource_type": normalized_type,
                },
            }

        if normalized_type == "fusion":
            fusion = self.fusion_handler.get_fusion(str(resource_id))
            if not fusion or str(fusion.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None
            selected_call = self.fusion_handler.get_selected_fusioncall(fusion)
            if not selected_call:
                return None
            gene1 = fusion.get("gene1")
            gene2 = fusion.get("gene2")
            return {
                "variant": f"{selected_call.get('breakpoint1', '')}^{selected_call.get('breakpoint2', '')}",
                "nomenclature": "f",
                "text": f"{gene1 or 'NA'}::{gene2 or 'NA'} auto-tiered resource",
                "variant_data": {
                    "gene1": gene1,
                    "gene2": gene2,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "resource_type": normalized_type,
                },
            }

        if normalized_type == "cnv":
            cnv = self.copy_number_variant_handler.get_cnv(str(resource_id))
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
                "text": f"{gene_label or resource_id} auto-tiered resource",
                "variant_data": {
                    "gene": gene_label,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "resource_type": normalized_type,
                },
            }

        if normalized_type == "translocation":
            transloc = self.translocation_handler.get_transloc(str(resource_id))
            if not transloc or str(transloc.get("SAMPLE_ID")) != str(sample.get("_id")):
                return None
            annotations = transloc.get("INFO", {}).get("MANE_ANN") or transloc.get("INFO", {}).get(
                "ANN", []
            )
            gene_label = None
            if annotations:
                first_annotation = annotations[0]
                gene_names = str(first_annotation.get("Gene_Name", "")).split("&")
                gene_label = "-".join([gene for gene in gene_names if gene])
            return {
                "variant": f"{transloc.get('CHROM')}:{transloc.get('POS')}^{transloc.get('ALT')}",
                "nomenclature": "t",
                "text": f"{gene_label or resource_id} auto-tiered resource",
                "variant_data": {
                    "gene": gene_label,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "resource_type": normalized_type,
                },
            }

        raise api_error(400, f"Unsupported resource_type: {resource_type}")

    def set_tier_bulk(
        self,
        *,
        sample: dict,
        resource_type: str,
        resource_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
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
            assay_group: Assay-group context for annotation text.
            subpanel: Optional subpanel context.
            apply: Whether to add or remove the classification.
            class_num: Target tier/class number.
            create_annotation_text_fn: Helper used to build default annotation text.
            create_classified_variant_doc_fn: Helper used to build classification documents.
        """
        bulk_docs: list[dict[str, Any]] = []
        for resource_id in resource_ids:
            identity = self._load_resource_identity(
                sample=sample,
                resource_type=resource_type,
                resource_id=str(resource_id),
                assay_group=assay_group,
                subpanel=subpanel,
                create_annotation_text_fn=create_annotation_text_fn,
            )
            if not identity:
                continue

            if not apply:
                self.annotation_handler.delete_classified_variant(
                    variant=identity["variant"],
                    nomenclature=identity["nomenclature"],
                    variant_data=identity["variant_data"],
                    class_num=class_num,
                    annotation_text=identity["text"],
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
            bulk_docs.append(
                deepcopy(
                    create_classified_variant_doc_fn(
                        variant=identity["variant"],
                        nomenclature=identity["nomenclature"],
                        class_num=class_num,
                        variant_data=identity["variant_data"],
                        text=identity["text"],
                        source="bulk_tier_default_text",
                    )
                )
            )

        if bulk_docs:
            self.annotation_handler.insert_annotation_bulk(bulk_docs)

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
            enriched_form = dict(form_data)
            enriched_form.setdefault("resource_type", self.normalize_resource_type(resource_type))
            self.annotation_handler.insert_classified_variant(
                variant, nomenclature, class_num, enriched_form
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
        enriched_form = dict(form_data)
        enriched_form.setdefault("resource_type", self.normalize_resource_type(resource_type))
        self.annotation_handler.delete_classified_variant(variant, nomenclature, enriched_form)


__all__ = ["ResourceClassificationService"]
