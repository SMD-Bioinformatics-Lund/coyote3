"""RNA route workflow service."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_managed_schema
from api.core.interpretation.annotation_enrichment import add_global_annotations
from api.core.interpretation.report_summary import generate_summary_text
from api.core.workflows.rna_workflow import RNAWorkflowService
from api.http import api_error, get_formatted_assay_config
from api.repositories.rna_repository import RnaRouteRepository, RnaWorkflowRepository
from api.runtime import app as runtime_app


class RnaService:
    """Own shared RNA and fusion support workflows."""

    def __init__(
        self,
        repository: RnaRouteRepository | None = None,
        workflow_repository: RnaWorkflowRepository | None = None,
    ) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
                workflow_repository: Workflow repository. Optional argument.
        """
        self.repository = repository or RnaRouteRepository()
        self.workflow_repository = workflow_repository or RnaWorkflowRepository()
        if not RNAWorkflowService.has_repository():
            RNAWorkflowService.set_repository(self.workflow_repository)

    @staticmethod
    def mutation_payload(
        sample_id: str, resource: str, resource_id: str, action: str
    ) -> dict[str, Any]:
        """Mutation payload.

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

    def list_fusions_payload(self, *, request, sample: dict, util_module) -> dict[str, Any]:
        """List fusions payload.

        Args:
            request: Value for ``request``.
            sample (dict): Value for ``sample``.
            util_module: Value for ``util_module``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")

        sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
            sample, assay_config, str(sample.get("_id")), runtime_app.logger
        )
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        assay_config_schema = build_managed_schema(aspc_spec_for_category("RNA"))
        assay_panel_doc = self.repository.asp_handler.get_asp(asp_name=sample.get("assay"))
        fusionlist_options = self.repository.isgl_handler.get_isgl_by_asp(
            sample.get("assay"), is_active=True, list_type="fusionlist"
        )
        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        has_hidden_comments = self.repository.sample_handler.hidden_sample_comments(
            sample.get("_id")
        )
        filter_context = RNAWorkflowService.compute_filter_context(
            sample=sample,
            sample_filters=sample_filters,
            assay_panel_doc=assay_panel_doc,
        )
        query = RNAWorkflowService.build_fusion_list_query(
            assay_group=assay_group,
            sample_id=str(sample["_id"]),
            sample_filters=sample_filters,
            filter_context=filter_context,
        )
        fusions = list(self.repository.fusion_handler.get_sample_fusions(query))
        fusions, tiered_fusions = add_global_annotations(fusions, assay_group, subpanel)
        sample = RNAWorkflowService.attach_rna_analysis_sections(sample)
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
        """Show fusion payload.

        Args:
            sample (dict): Value for ``sample``.
            fusion_id (str): Value for ``fusion_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        fusion = self.repository.fusion_handler.get_fusion(fusion_id)
        if not fusion:
            raise api_error(404, "Fusion not found")
        if str(fusion.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Fusion not found for sample")

        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        show_context = RNAWorkflowService.build_show_fusion_context(fusion, assay_group, subpanel)
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
