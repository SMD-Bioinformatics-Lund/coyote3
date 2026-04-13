"""RNA route workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.http import api_error, get_formatted_assay_config, setup_error
from api.runtime_state import app as runtime_app
from api.services.interpretation.annotation_enrichment import add_global_annotations
from api.services.interpretation.report_summary import generate_summary_text
from api.services.reporting.rna_workflow import RNAWorkflowService


class RnaService:
    """Own shared RNA and fusion support workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "RnaService":
        """Build the service from the shared store."""
        return cls(
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            sample_handler=store.sample_handler,
            fusion_handler=store.fusion_handler,
            rna_expression_handler=store.rna_expression_handler,
            rna_classification_handler=store.rna_classification_handler,
            rna_quality_handler=store.rna_quality_handler,
            annotation_handler=store.annotation_handler,
            reported_variant_handler=store.reported_variant_handler,
        )

    def __init__(
        self,
        *,
        assay_panel_handler: Any,
        gene_list_handler: Any,
        sample_handler: Any,
        fusion_handler: Any,
        rna_expression_handler: Any,
        rna_classification_handler: Any,
        rna_quality_handler: Any,
        annotation_handler: Any,
        reported_variant_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.sample_handler = sample_handler
        self.fusion_handler = fusion_handler
        self.rna_expression_handler = rna_expression_handler
        self.rna_classification_handler = rna_classification_handler
        self.rna_quality_handler = rna_quality_handler
        self.annotation_handler = annotation_handler
        self.workflow = RNAWorkflowService(
            sample_handler=sample_handler,
            gene_list_handler=gene_list_handler,
            rna_expression_handler=rna_expression_handler,
            rna_classification_handler=rna_classification_handler,
            rna_quality_handler=rna_quality_handler,
            fusion_handler=fusion_handler,
            annotation_handler=annotation_handler,
            assay_panel_handler=assay_panel_handler,
            reported_variant_handler=reported_variant_handler,
        )

    def list_fusions_payload(self, *, request, sample: dict, util_module) -> dict[str, Any]:
        """Return the fusion-list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.
            util_module: Shared utility module used by the route layer.

        Returns:
            dict[str, Any]: Fusion list payload with filters and summary data.
        """
        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during RNA fusion loading."
                ),
            )

        sample, sample_filters = self.workflow.merge_and_normalize_sample_filters(
            sample, assay_config, str(sample.get("_id")), runtime_app.logger
        )
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        assay_config_schema = build_form_spec(aspc_spec_for_category("RNA"))
        assay_panel_doc = self.assay_panel_handler.get_asp(asp_name=sample.get("assay"))
        fusionlist_options = self.gene_list_handler.get_isgl_by_asp(
            sample.get("assay"), is_active=True, list_type="fusion_genelist"
        )
        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        has_hidden_comments = self.sample_handler.hidden_sample_comments(sample.get("_id"))
        filter_context = self.workflow.compute_filter_context(
            sample=sample,
            sample_filters=sample_filters,
            assay_panel_doc=assay_panel_doc,
        )
        query = self.workflow.build_fusion_list_query(
            assay_group=assay_group,
            sample_id=str(sample["_id"]),
            sample_filters=sample_filters,
            filter_context=filter_context,
        )
        fusions = list(self.fusion_handler.get_sample_fusions(query))
        fusions, tiered_fusions = add_global_annotations(
            fusions,
            assay_group,
            subpanel,
            annotation_handler=self.annotation_handler,
        )
        sample = self.workflow.attach_rna_analysis_sections(sample)
        ai_text = generate_summary_text(
            sample_ids,
            assay_config,
            assay_panel_doc,
            {"fusions": tiered_fusions},
            filter_context["filter_genes"],
            filter_context["checked_fusionlists"],
        )
        return {
            "sample": sample,
            "meta": {
                "request_path": request.url.path,
                "count": len(fusions),
                "tiered": tiered_fusions,
            },
            "assay_group": assay_group,
            "subpanel": subpanel,
            "analysis_sections": assay_config.get("analysis_types", []),
            "assay_config": assay_config,
            "assay_config_schema": assay_config_schema,
            "assay_panel_doc": assay_panel_doc,
            "sample_ids": sample_ids,
            "hidden_comments": has_hidden_comments,
            "fusionlist_options": fusionlist_options,
            "checked_fusionlists": filter_context.get("checked_fusionlists", []),
            "checked_fusionlists_dict": filter_context.get("genes_covered_in_panel", {}),
            "filters": sample_filters,
            "filter_context": filter_context,
            "fusions": fusions,
            "ai_text": ai_text,
        }

    def show_fusion_payload(self, *, sample: dict, fusion_id: str) -> dict[str, Any]:
        """Return the detail payload for a single fusion.

        Args:
            sample: Sample payload owning the fusion.
            fusion_id: Fusion identifier to load.

        Returns:
            dict[str, Any]: Fusion detail payload for the UI.
        """
        fusion = self.fusion_handler.get_fusion(fusion_id)
        if not fusion:
            raise api_error(404, "Fusion not found")
        if str(fusion.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Fusion not found for sample")

        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during RNA fusion detail loading."
                ),
            )
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        show_context = self.workflow.build_show_fusion_context(
            fusion,
            assay_group,
            subpanel,
        )
        return {
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "assay_group": assay_group,
                "subpanel": subpanel,
            },
            "fusion": show_context["fusion"],
            "in_other": show_context["in_other"],
            "annotations": show_context["annotations"],
            "latest_classification": show_context["latest_classification"],
            "annotations_interesting": show_context["annotations_interesting"],
            "other_classifications": show_context["other_classifications"],
            "has_hidden_comments": show_context["hidden_comments"],
            "hidden_comments": show_context["hidden_comments"],
            "assay_group": assay_group,
            "subpanel": subpanel,
            "assay_group_mappings": show_context["assay_group_mappings"],
        }

    def set_fusion_flag(self, *, fusion_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single fusion."""
        if flag == "false_positive":
            if apply:
                self.fusion_handler.mark_false_positive_fusion(fusion_id)
            else:
                self.fusion_handler.unmark_false_positive_fusion(fusion_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def select_fusion_call(self, *, fusion_id: str, callidx: str, num_calls: str) -> None:
        """Persist the selected call index for a fusion."""
        self.fusion_handler.pick_fusion(fusion_id, callidx, num_calls)

    def set_fusion_comment_hidden(self, *, fusion_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a fusion comment."""
        if hidden:
            self.fusion_handler.hide_fus_comment(fusion_id, comment_id)
            return
        self.fusion_handler.unhide_fus_comment(fusion_id, comment_id)

    def set_fusion_bulk_flag(self, *, fusion_ids: list[str], apply: bool, flag: str) -> None:
        """Apply or remove a bulk boolean flag on fusions."""
        if not fusion_ids:
            return
        if flag == "false_positive":
            self.fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
            return
        if flag == "irrelevant":
            self.fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
            return
        raise ValueError(f"Unsupported flag: {flag}")
