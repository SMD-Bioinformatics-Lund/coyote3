"""DNA application service for small-variant workflows."""

from __future__ import annotations

from typing import Any

from api.application.dna.payloads import (
    biomarkers_payload as _biomarkers_payload,
)
from api.application.dna.payloads import (
    list_variants_payload as _list_variants_payload,
)
from api.application.dna.payloads import (
    plot_context_payload as _plot_context_payload,
)
from api.application.dna.payloads import (
    variant_context_payload as _variant_context_payload,
)
from api.application.dna.variant_classification import classify_variant as _classify_variant
from api.application.dna.variant_classification import (
    remove_classified_variant as _remove_classified_variant,
)
from api.application.dna.variant_classification import (
    set_variant_tier_bulk as _set_variant_tier_bulk,
)
from api.application.dna.variant_comments import add_variant_comment as _add_variant_comment
from api.application.dna.variant_exports import (
    build_cnv_export_rows as _build_cnv_export_rows,
)
from api.application.dna.variant_exports import (
    build_snv_export_rows as _build_snv_export_rows,
)
from api.application.dna.variant_exports import (
    build_transloc_export_rows as _build_transloc_export_rows,
)
from api.application.dna.variant_exports import export_rows_to_csv as _export_rows_to_csv
from api.application.dna.variant_state import blacklist_variant as _blacklist_variant
from api.application.dna.variant_state import coerce_bool as _coerce_bool
from api.application.dna.variant_state import (
    require_variant_for_sample as _require_variant_for_sample,
)
from api.application.dna.variant_state import set_variant_bulk_flag as _set_variant_bulk_flag
from api.application.dna.variant_state import (
    set_variant_comment_hidden as _set_variant_comment_hidden,
)
from api.application.dna.variant_state import set_variant_flag as _set_variant_flag
from api.application.dna.variant_state import (
    set_variant_override_blacklist as _set_variant_override_blacklist,
)
from api.config.database_versions import sample_vep_version
from api.contracts.operations import OperationResult
from api.domain.core.dna.cnvqueries import build_cnv_query
from api.domain.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist


class DnaService:
    """Own common DNA, CNV, and small-variant support workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "DnaService":
        """Build the service from the runtime store."""
        return cls(
            assay_panel_repository=store.assay_panel_repository,
            gene_list_repository=store.gene_list_repository,
            variant_repository=store.variant_repository,
            anno_vep_repository=store.anno_vep_repository,
            blacklist_repository=store.blacklist_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            oncokb_repository=store.oncokb_repository,
            annotation_repository=store.annotation_repository,
            fusion_repository=store.fusion_repository,
            translocation_repository=store.translocation_repository,
            biomarker_repository=store.biomarker_repository,
            bam_record_repository=store.bam_record_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            sample_repository=store.sample_repository,
            expression_repository=store.expression_repository,
            civic_repository=store.civic_repository,
            brca_repository=store.brca_repository,
            iarc_tp53_repository=store.iarc_tp53_repository,
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
        )

    def __init__(
        self,
        *,
        assay_panel_repository: Any,
        gene_list_repository: Any,
        variant_repository: Any,
        anno_vep_repository: Any,
        blacklist_repository: Any,
        copy_number_variant_repository: Any,
        oncokb_repository: Any,
        annotation_repository: Any,
        fusion_repository: Any,
        translocation_repository: Any,
        biomarker_repository: Any,
        bam_record_repository: Any,
        vep_metadata_repository: Any,
        sample_repository: Any,
        expression_repository: Any,
        civic_repository: Any,
        brca_repository: Any,
        iarc_tp53_repository: Any,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_panel_repository = assay_panel_repository
        self.gene_list_repository = gene_list_repository
        self.variant_repository = variant_repository
        self.anno_vep_repository = anno_vep_repository
        self.blacklist_repository = blacklist_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.oncokb_repository = oncokb_repository
        self.oncokb_public_cache_repository = oncokb_public_cache_repository
        self.clinpgx_public_repository = clinpgx_public_repository
        self.annotation_repository = annotation_repository
        self.fusion_repository = fusion_repository
        self.translocation_repository = translocation_repository
        self.biomarker_repository = biomarker_repository
        self.bam_record_repository = bam_record_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.sample_repository = sample_repository
        self.expression_repository = expression_repository
        self.civic_repository = civic_repository
        self.brca_repository = brca_repository
        self.iarc_tp53_repository = iarc_tp53_repository

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
        cnvs = list(self.copy_number_variant_repository.get_sample_cnvs(cnv_query))
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

    def set_variant_bulk_flag(
        self, *, resource_ids: list[str], apply: bool, flag: str
    ) -> OperationResult:
        """Apply or remove a bulk boolean flag on variants.

        Args:
            resource_ids: Variant identifiers to update.
            apply: Whether to add or remove the flag.
            flag: Flag name to apply.
        """
        return _set_variant_bulk_flag(self, resource_ids=resource_ids, apply=apply, flag=flag)

    def set_variant_flag(self, *, var_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single variant."""
        _set_variant_flag(self, var_id=var_id, apply=apply, flag=flag)

    def select_variant_transcript(
        self,
        *,
        sample: dict[str, Any],
        var_id: str,
        feature_id: str,
    ) -> OperationResult:
        """Set the displayed transcript for a small variant from the VEP vault."""
        variant = self.require_variant_for_sample(sample=sample, var_id=var_id)
        feature = str(feature_id or "").strip()
        if not feature:
            return OperationResult.failed("feature_id is required")
        vep_version = sample_vep_version(sample)
        if not vep_version:
            return OperationResult.failed("sample has no VEP version metadata")
        vault = self.anno_vep_repository.get_for_variant(
            simple_id_hash=variant.get("simple_id_hash"),
            vep_version=vep_version,
        )
        if not vault:
            return OperationResult.failed(
                "no transcript vault entry exists for this variant/version"
            )
        selected = next(
            (
                dict(csq)
                for csq in vault.get("CSQ") or []
                if str(csq.get("Feature") or "").strip() == feature
            ),
            None,
        )
        if not selected:
            return OperationResult.failed("requested transcript is not available for this variant")
        alternate = [
            dict(csq)
            for csq in vault.get("CSQ") or []
            if str(csq.get("Feature") or "").strip() != feature
        ]
        operation = self.variant_repository.update_selected_transcript(
            var_id=var_id,
            selected_csq=selected,
            alternate_csq=alternate,
            selected_feature=feature,
            criteria="manual_override",
        )
        return operation

    def blacklist_variant(self, *, variant: dict[str, Any], assay_group: str) -> OperationResult:
        """Create a blacklist entry for a variant in an assay group."""
        return _blacklist_variant(self, variant=variant, assay_group=assay_group)

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
        paginate: bool = True,
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
            paginate=paginate,
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
            util_module: Common utility module used by the route layer.
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
