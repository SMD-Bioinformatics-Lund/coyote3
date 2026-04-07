"""DNA application service for small-variant workflows."""

from __future__ import annotations

from typing import Any

from api.core.dna.cnvqueries import build_cnv_query
from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.services.dna.payloads import (
    biomarkers_payload as _biomarkers_payload,
)
from api.services.dna.payloads import (
    list_variants_payload as _list_variants_payload,
)
from api.services.dna.payloads import (
    plot_context_payload as _plot_context_payload,
)
from api.services.dna.payloads import (
    variant_context_payload as _variant_context_payload,
)
from api.services.dna.variant_classification import classify_variant as _classify_variant
from api.services.dna.variant_classification import (
    remove_classified_variant as _remove_classified_variant,
)
from api.services.dna.variant_classification import (
    set_variant_tier_bulk as _set_variant_tier_bulk,
)
from api.services.dna.variant_comments import add_variant_comment as _add_variant_comment
from api.services.dna.variant_exports import (
    build_cnv_export_rows as _build_cnv_export_rows,
)
from api.services.dna.variant_exports import (
    build_snv_export_rows as _build_snv_export_rows,
)
from api.services.dna.variant_exports import (
    build_transloc_export_rows as _build_transloc_export_rows,
)
from api.services.dna.variant_exports import export_rows_to_csv as _export_rows_to_csv
from api.services.dna.variant_state import blacklist_variant as _blacklist_variant
from api.services.dna.variant_state import coerce_bool as _coerce_bool
from api.services.dna.variant_state import require_variant_for_sample as _require_variant_for_sample
from api.services.dna.variant_state import set_variant_bulk_flag as _set_variant_bulk_flag
from api.services.dna.variant_state import set_variant_comment_hidden as _set_variant_comment_hidden
from api.services.dna.variant_state import set_variant_flag as _set_variant_flag
from api.services.dna.variant_state import (
    set_variant_override_blacklist as _set_variant_override_blacklist,
)


class DnaService:
    """Own shared DNA, CNV, and small-variant support workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "DnaService":
        """Build the service from the shared store."""
        return cls(
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            variant_handler=store.variant_handler,
            blacklist_handler=store.blacklist_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            oncokb_handler=store.oncokb_handler,
            annotation_handler=store.annotation_handler,
            fusion_handler=store.fusion_handler,
            translocation_handler=store.translocation_handler,
            biomarker_handler=store.biomarker_handler,
            bam_record_handler=store.bam_record_handler,
            vep_metadata_handler=store.vep_metadata_handler,
            sample_handler=store.sample_handler,
            expression_handler=store.expression_handler,
            civic_handler=store.civic_handler,
            brca_handler=store.brca_handler,
            iarc_tp53_handler=store.iarc_tp53_handler,
        )

    def __init__(
        self,
        *,
        assay_panel_handler: Any,
        gene_list_handler: Any,
        variant_handler: Any,
        blacklist_handler: Any,
        copy_number_variant_handler: Any,
        oncokb_handler: Any,
        annotation_handler: Any,
        fusion_handler: Any,
        translocation_handler: Any,
        biomarker_handler: Any,
        bam_record_handler: Any,
        vep_metadata_handler: Any,
        sample_handler: Any,
        expression_handler: Any,
        civic_handler: Any,
        brca_handler: Any,
        iarc_tp53_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.variant_handler = variant_handler
        self.blacklist_handler = blacklist_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.oncokb_handler = oncokb_handler
        self.annotation_handler = annotation_handler
        self.fusion_handler = fusion_handler
        self.translocation_handler = translocation_handler
        self.biomarker_handler = biomarker_handler
        self.bam_record_handler = bam_record_handler
        self.vep_metadata_handler = vep_metadata_handler
        self.sample_handler = sample_handler
        self.expression_handler = expression_handler
        self.civic_handler = civic_handler
        self.brca_handler = brca_handler
        self.iarc_tp53_handler = iarc_tp53_handler

    @staticmethod
    def export_rows_to_csv(rows: list[Any]) -> str:
        """Serialize export rows into CSV text with stable column ordering."""
        return _export_rows_to_csv(rows)

    def build_snv_export_rows(self, variants: list[dict[str, Any]]) -> list[Any]:
        """Build typed SNV export rows from filtered variant documents."""
        return _build_snv_export_rows(variants)

    def build_cnv_export_rows(
        self, cnvs: list[dict[str, Any]], sample: dict[str, Any], assay_group: str
    ) -> list[Any]:
        """Build typed CNV export rows from filtered CNV documents."""
        return _build_cnv_export_rows(cnvs, sample, assay_group)

    def build_transloc_export_rows(self, translocs: list[dict[str, Any]]) -> list[Any]:
        """Build typed translocation export rows from filtered translocation documents."""
        return _build_transloc_export_rows(translocs)

    def load_cnvs_for_sample(
        self,
        *,
        sample: dict,
        sample_filters: dict,
        filter_genes: list[str],
    ) -> list[dict]:
        """Load CNVs for a sample using the active filters.

        Args:
            sample: Sample payload to inspect.
            sample_filters: Active sample filters.
            filter_genes: Effective genes selected for the sample.

        Returns:
            list[dict]: Filtered CNV documents for the sample.
        """
        cnv_query = build_cnv_query(
            str(sample["_id"]),
            filters={**sample_filters, "filter_genes": filter_genes},
        )
        cnvs = list(self.copy_number_variant_handler.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def require_variant_for_sample(self, *, sample: dict, var_id: str) -> dict:
        """Load a variant and assert it belongs to the provided sample.

        Args:
            sample: Sample payload expected to own the variant.
            var_id: Variant identifier to resolve.

        Returns:
            dict: Variant document belonging to the sample.
        """
        return _require_variant_for_sample(self, sample=sample, var_id=var_id)

    def set_variant_bulk_flag(self, *, resource_ids: list[str], apply: bool, flag: str) -> None:
        """Apply or remove a bulk boolean flag on variants.

        Args:
            resource_ids: Variant identifiers to update.
            apply: Whether to add or remove the flag.
            flag: Flag name to apply.
        """
        _set_variant_bulk_flag(self, resource_ids=resource_ids, apply=apply, flag=flag)

    def set_variant_flag(self, *, var_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single variant."""
        _set_variant_flag(self, var_id=var_id, apply=apply, flag=flag)

    def blacklist_variant(self, *, variant: dict[str, Any], assay_group: str) -> None:
        """Create a blacklist entry for a variant in an assay group."""
        _blacklist_variant(self, variant=variant, assay_group=assay_group)

    def set_variant_override_blacklist(self, *, var_id: str, override: bool) -> None:
        """Apply or remove the blacklist-override flag on a small variant."""
        _set_variant_override_blacklist(self, var_id=var_id, override=override)

    def set_variant_comment_hidden(self, *, var_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a variant comment."""
        _set_variant_comment_hidden(self, var_id=var_id, comment_id=comment_id, hidden=hidden)

    def set_variant_tier_bulk(
        self,
        *,
        sample: dict,
        resource_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
        apply: bool,
        class_num: int,
        create_annotation_text_fn,
        create_classified_variant_doc_fn,
    ) -> None:
        """Apply or remove variant classifications in bulk.

        Args:
            sample: Sample payload containing ownership context.
            resource_ids: Variant identifiers to update.
            assay_group: Assay-group context for annotation text.
            subpanel: Optional subpanel context.
            apply: Whether to add or remove the classification.
            class_num: Target tier/class number.
            create_annotation_text_fn: Helper used to build default annotation text.
            create_classified_variant_doc_fn: Helper used to build classification documents.
        """
        _set_variant_tier_bulk(
            self,
            sample=sample,
            resource_ids=resource_ids,
            assay_group=assay_group,
            subpanel=subpanel,
            apply=apply,
            class_num=class_num,
            create_annotation_text_fn=create_annotation_text_fn,
            create_classified_variant_doc_fn=create_classified_variant_doc_fn,
        )

    def classify_variant(
        self, *, form_data: dict, get_tier_classification_fn, get_variant_nomenclature_fn
    ) -> None:
        """Classify a variant and persist classification documents."""
        _classify_variant(
            self,
            form_data=form_data,
            get_tier_classification_fn=get_tier_classification_fn,
            get_variant_nomenclature_fn=get_variant_nomenclature_fn,
        )

    def remove_classified_variant(self, *, form_data: dict, get_variant_nomenclature_fn) -> None:
        """Remove a classified variant document."""
        _remove_classified_variant(
            self,
            form_data=form_data,
            get_variant_nomenclature_fn=get_variant_nomenclature_fn,
        )

    def add_variant_comment(
        self, *, form_data: dict, target_id: str, get_variant_nomenclature_fn, create_comment_doc_fn
    ) -> str:
        """Create a variant/fusion/translocation/CNV comment and return its resource type.

        Args:
            form_data: Submitted comment form payload.
            target_id: Resource identifier to comment on.
            get_variant_nomenclature_fn: Helper that resolves nomenclature and variant label.
            create_comment_doc_fn: Helper that builds the comment document.

        Returns:
            str: Comment resource type used in the change payload.
        """
        return _add_variant_comment(
            self,
            form_data=form_data,
            target_id=target_id,
            get_variant_nomenclature_fn=get_variant_nomenclature_fn,
            create_comment_doc_fn=create_comment_doc_fn,
        )

    def list_variants_payload(
        self,
        *,
        request,
        sample: dict,
        util_module,
        add_global_annotations_fn,
        generate_summary_text_fn,
        build_query_fn,
        get_filter_conseq_terms_fn,
        assay_config_getter,
    ) -> dict[str, Any]:
        """Return the small-variant list payload for a sample."""
        return _list_variants_payload(
            service=self,
            request=request,
            sample=sample,
            util_module=util_module,
            add_global_annotations_fn=add_global_annotations_fn,
            generate_summary_text_fn=generate_summary_text_fn,
            build_query_fn=build_query_fn,
            get_filter_conseq_terms_fn=get_filter_conseq_terms_fn,
            assay_config_getter=assay_config_getter,
        )

    def plot_context_payload(self, *, sample: dict, assay_config_getter) -> dict[str, Any]:
        """Build plot context payload for DNA routes.

        Args:
            sample: Sample payload to inspect.
            assay_config_getter: Helper that resolves assay configuration.

        Returns:
            dict[str, Any]: Plot-context payload for DNA routes.
        """
        return _plot_context_payload(
            service=self,
            sample=sample,
            assay_config_getter=assay_config_getter,
        )

    def biomarkers_payload(self, *, sample: dict) -> dict[str, Any]:
        """Build biomarker payload for DNA routes.

        Args:
            sample: Sample payload to inspect.

        Returns:
            dict[str, Any]: Biomarker payload for DNA routes.
        """
        return _biomarkers_payload(service=self, sample=sample)

    def variant_context_payload(
        self,
        *,
        sample: dict,
        var_id: str,
        add_alt_class_fn,
        util_module,
        assay_config_getter,
    ) -> dict[str, Any]:
        """Build single-variant context payload for DNA routes.

        Args:
            sample: Sample payload owning the variant.
            var_id: Variant identifier to load.
            add_alt_class_fn: Helper used to add alternate classifications.
            util_module: Shared utility module used by the route layer.
            assay_config_getter: Helper that resolves assay configuration.

        Returns:
            dict[str, Any]: Variant-context payload for DNA routes.
        """
        return _variant_context_payload(
            service=self,
            sample=sample,
            var_id=var_id,
            add_alt_class_fn=add_alt_class_fn,
            util_module=util_module,
            assay_config_getter=assay_config_getter,
        )

    @staticmethod
    def coerce_bool(value: object, default: bool = True) -> bool:
        """Convert arbitrary input into a boolean.

        Args:
            value: Raw value to coerce.
            default: Fallback value when coercion fails.

        Returns:
            bool: Coerced boolean value.
        """
        return _coerce_bool(value, default=default)
