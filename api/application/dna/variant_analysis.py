"""DNA application service for small-variant workflows."""

from __future__ import annotations

from functools import partial
from typing import Any

from api.application.dna import (
    export,
    payloads,
    variant_state,
)
from api.application.interpretation.annotation_enrichment import add_global_annotations
from api.application.query_rules.service import QueryRuleService, effective_policy
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.config.database_versions import require_sample_vep_version, sample_vep_version
from api.contracts.operations import OperationResult
from api.domain.core.dna.cnvqueries import build_cnv_query, include_normal_cnvs
from api.domain.core.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
    get_filter_conseq_terms,
)
from api.domain.core.dna.transcript_payloads import compact_selected_csq
from api.domain.core.dna.varqueries import build_query
from api.infra.observability.operations import measured_operation


class DnaService:
    """Own common DNA, CNV, and small-variant support workflows."""

    def export_source_payload(
        self,
        *,
        request: Any,
        sample: dict[str, Any],
        util_module: Any,
        assay_config_getter: Any,
    ) -> dict[str, Any]:
        """Build the shared unpaginated DNA export context with injected repositories.

        Args:
            request: Export request supplying active search and sorting parameters.
            sample: Authorized sample whose current filters apply.
            util_module: Existing serialization and clinical utility dependencies.
            assay_config_getter: Resolver for the sample's effective assay configuration.

        Returns:
            The established DNA context including structural finding sections.
        """

        def consequence_terms(values: list[str]) -> list[str]:
            """Resolve consequence metadata only when the export query requests it."""
            metadata = self.vep_metadata_repository.get_consequence_group_map(
                str(require_sample_vep_version(sample))
            )
            return get_filter_conseq_terms(values, metadata)

        return self.list_variants_payload(
            request=request,
            sample=sample,
            util_module=util_module,
            add_global_annotations_fn=partial(
                add_global_annotations, annotation_repository=self.annotation_repository
            ),
            build_query_fn=build_query,
            get_filter_conseq_terms_fn=consequence_terms,
            assay_config_getter=assay_config_getter,
            paginate=False,
        )

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
            cosmic_repository=store.cosmic_repository,
            hgnc_repository=getattr(store, "hgnc_repository", None),
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
            clinical_rule_service=ClinicalRuleService.from_store(store),
            query_rule_service=QueryRuleService.from_store(store),
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
        cosmic_repository: Any,
        hgnc_repository: Any | None = None,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
        clinical_rule_service: ClinicalRuleService | None = None,
        query_rule_service=None,
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
        self.cosmic_repository = cosmic_repository
        self.hgnc_repository = hgnc_repository
        self.clinical_rule_service = clinical_rule_service
        self.query_rule_service = query_rule_service

    @staticmethod
    def export_rows_to_csv(rows: list[Any]) -> str:
        """Serialize export rows into CSV text with stable column ordering."""
        return export.export_rows_to_csv(rows)

    def build_snv_export_rows(self, variants: list[dict[str, Any]]) -> list[Any]:
        """Build typed SNV export rows from filtered variant documents."""
        return export.build_snv_export_rows(variants)

    def build_cnv_export_rows(
        self, cnvs: list[dict[str, Any]], sample: dict[str, Any], assay_group: str
    ) -> list[Any]:
        """Build typed CNV export rows from filtered CNV documents."""
        return export.build_cnv_export_rows(cnvs, sample, assay_group)

    def build_transloc_export_rows(self, translocs: list[dict[str, Any]]) -> list[Any]:
        """Build typed translocation export rows from filtered translocation documents."""
        return export.build_transloc_export_rows(translocs)

    def load_cnvs_for_sample(
        self,
        *,
        sample: dict,
        sample_filters: dict,
        filter_genes: list[str],
        assay_group: str | None = None,
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
            filters={
                **sample_filters,
                "filter_genes": filter_genes,
                "assay_group": assay_group or sample.get("asp_group"),
                "asp_id": sample.get("asp_id"),
                "diagnosis_id": sample.get("diagnosis_id"),
                "intent": "somatic",
            },
            include_normal=include_normal_cnvs(sample),
            policy=effective_policy(
                self.query_rule_service, "cnv", sample, assay_group=assay_group
            ),
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
        return variant_state.require_variant_for_sample(self, sample=sample, var_id=var_id)

    def set_variant_bulk_flag(
        self, *, sample: dict, resource_ids: list[str], apply: bool, flag: str
    ) -> OperationResult:
        """Apply or remove a bulk boolean flag on variants.

        Args:
            sample: Authorized sample that must own every selected variant.
            resource_ids: Variant identifiers to update.
            apply: Whether to add or remove the flag.
            flag: Flag name to apply.
        """
        for resource_id in resource_ids:
            self.require_variant_for_sample(sample=sample, var_id=resource_id)
        return variant_state.set_variant_bulk_flag(
            self, sample=sample, resource_ids=resource_ids, apply=apply, flag=flag
        )

    def set_variant_flag(
        self, *, sample: dict, var_id: str, apply: bool, flag: str
    ) -> OperationResult:
        """Set an allowed flag using the authorized sample in the write predicate."""
        fields = {"interesting": "interesting", "false_positive": "fp", "irrelevant": "irrelevant"}
        if flag not in fields:
            raise ValueError(f"Unsupported flag: {flag}")
        return self.variant_repository.set_sample_finding_flag(
            sample_id=str(sample["_id"]), resource_ids=[var_id], flag=fields[flag], value=apply
        )

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
        operation = self.variant_repository.update_selected_transcript(
            var_id=var_id,
            selected_csq=compact_selected_csq(selected),
            selected_feature=feature,
            criteria="manual_override",
        )
        return operation

    def blacklist_variant(self, *, variant: dict[str, Any], assay_group: str) -> OperationResult:
        """Create a blacklist entry for a variant in an assay group."""
        return variant_state.blacklist_variant(self, variant=variant, assay_group=assay_group)

    def set_variant_override_blacklist(
        self, *, sample: dict, var_id: str, override: bool
    ) -> OperationResult:
        """Set blacklist override only within the authorized sample."""
        return self.variant_repository.set_sample_finding_flag(
            sample_id=str(sample["_id"]),
            resource_ids=[var_id],
            flag="override_blacklist",
            value=override,
        )

    def set_variant_comment_hidden(self, *, var_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a variant comment."""
        variant_state.set_variant_comment_hidden(
            self, var_id=var_id, comment_id=comment_id, hidden=hidden
        )

    @measured_operation("query.variants")
    def list_variants_payload(
        self,
        *,
        request,
        sample: dict,
        util_module,
        add_global_annotations_fn,
        build_query_fn,
        get_filter_conseq_terms_fn,
        assay_config_getter,
        paginate: bool = True,
    ) -> dict[str, Any]:
        """Return the small-variant list payload for a sample."""
        return payloads.list_variants_payload(
            service=self,
            request=request,
            sample=sample,
            util_module=util_module,
            add_global_annotations_fn=add_global_annotations_fn,
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
        return payloads.plot_context_payload(
            service=self,
            sample=sample,
            assay_config_getter=assay_config_getter,
        )

    def biomarkers_payload(self, *, sample: dict, assay_config_getter) -> dict[str, Any]:
        """Return measurements enabled by the sample's stored ASPC.

        Args:
            sample: Sample payload to inspect.
            assay_config_getter: Resolver for the sample's recorded configuration revision.

        Returns:
            dict[str, Any]: Biomarker payload for DNA routes.
        """
        return payloads.biomarkers_payload(
            service=self, sample=sample, assay_config_getter=assay_config_getter
        )

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
        return payloads.variant_context_payload(
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
        return variant_state.coerce_bool(value, default=default)
