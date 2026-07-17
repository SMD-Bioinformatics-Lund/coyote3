"""RNA route workflow service."""

from __future__ import annotations

import logging
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.common.pagination import paginate_items, request_pagination
from api.application.dna.export import export_rows_to_csv, join_tokens, safe_text, yes_no
from api.application.interpretation.annotation_enrichment import add_global_annotations
from api.application.interpretation.report_summary import generate_summary_text
from api.application.reporting.rna_workflow import RNAWorkflowService
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.contracts.operations import OperationResult
from api.contracts.rna import RnaFusionExportRow
from api.domain.common.errors import api_error, setup_error

logger = logging.getLogger(__name__)


class RnaService:
    """Own common RNA and fusion support workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "RnaService":
        """Build the service from the runtime store."""
        return cls(
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            gene_list_repository=store.gene_list_repository,
            sample_repository=store.sample_repository,
            fusion_repository=store.fusion_repository,
            rna_expression_repository=store.rna_expression_repository,
            rna_classification_repository=store.rna_classification_repository,
            rna_quality_repository=store.rna_quality_repository,
            annotation_repository=store.annotation_repository,
            reported_variant_repository=store.reported_variant_repository,
        )

    def __init__(
        self,
        *,
        assay_panel_repository: Any,
        assay_configuration_repository: Any | None = None,
        gene_list_repository: Any,
        sample_repository: Any,
        fusion_repository: Any,
        rna_expression_repository: Any,
        rna_classification_repository: Any,
        rna_quality_repository: Any,
        annotation_repository: Any,
        reported_variant_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.gene_list_repository = gene_list_repository
        self.sample_repository = sample_repository
        self.fusion_repository = fusion_repository
        self.rna_expression_repository = rna_expression_repository
        self.rna_classification_repository = rna_classification_repository
        self.rna_quality_repository = rna_quality_repository
        self.annotation_repository = annotation_repository
        self.workflow = RNAWorkflowService(
            sample_repository=sample_repository,
            gene_list_repository=gene_list_repository,
            rna_expression_repository=rna_expression_repository,
            rna_classification_repository=rna_classification_repository,
            rna_quality_repository=rna_quality_repository,
            fusion_repository=fusion_repository,
            annotation_repository=annotation_repository,
            assay_panel_repository=assay_panel_repository,
            reported_variant_repository=reported_variant_repository,
        )

    def _get_formatted_assay_config(self, sample: dict) -> dict:
        """Resolve formatted assay config using injected repositories when available."""
        if self.assay_configuration_repository is None:
            return get_formatted_assay_config(sample)
        return get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )

    def list_fusions_payload(
        self, *, request, sample: dict, util_module, paginate: bool = True
    ) -> dict[str, Any]:
        """Return the fusion-list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.
            util_module: Common utility module used by the route layer.

        Returns:
            dict[str, Any]: Fusion list payload with filters and summary data.
        """
        assay_config = self._get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during RNA fusion loading."
                ),
            )

        sample, sample_filters = self.workflow.merge_and_normalize_sample_filters(
            sample, assay_config, str(sample.get("_id")), logger
        )
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel_id")
        assay_config_schema = build_form_spec(aspc_spec_for_category("RNA"))
        assay_panel_doc = self.assay_panel_repository.get_asp(asp_name=sample.get("assay"))
        fusionlist_options = self.gene_list_repository.get_isgl_by_asp(
            sample.get("assay"), is_active=True, adhoc=False, list_type="fusion"
        )
        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        has_hidden_comments = self.sample_repository.hidden_sample_comments(sample.get("_id"))
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
        fusions = list(self.fusion_repository.get_sample_fusions(query))
        fusions, tiered_fusions = add_global_annotations(
            fusions,
            assay_group,
            subpanel,
            annotation_repository=self.annotation_repository,
        )
        page_fusions = fusions
        pagination_meta: dict[str, Any] = {
            "total": len(fusions),
            "count": len(fusions),
            "page_count": len(fusions),
            "page": 1,
            "per_page": len(fusions) or 50,
            "has_previous": False,
            "has_next": False,
        }
        if paginate:
            page, per_page = request_pagination(request)
            page_fusions, pagination_meta = paginate_items(fusions, page=page, per_page=per_page)
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
                **pagination_meta,
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
            "fusions": page_fusions,
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
        fusion = self.fusion_repository.get_fusion(fusion_id)
        if not fusion:
            raise api_error(404, "Fusion not found")
        if str(fusion.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Fusion not found for sample")

        assay_config = self._get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during RNA fusion detail loading."
                ),
            )
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel_id")
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

    def build_fusion_export_rows(self, fusions: list[dict[str, Any]]) -> list[RnaFusionExportRow]:
        """Build typed fusion export rows from filtered fusion documents."""
        rows: list[RnaFusionExportRow] = []
        for fusion in fusions:
            calls = fusion.get("calls") if isinstance(fusion.get("calls"), list) else []
            selected_call = next(
                (
                    call
                    for call in calls
                    if call.get("selected") == 1 or call.get("selected") is True
                ),
                calls[0] if calls else {},
            )
            genes = self._fusion_genes(fusion)
            comments = fusion.get("comments") or []
            latest_comment = comments[-1] if comments else {}
            classification = fusion.get("classification") or {}
            tier = classification.get("class")
            breakpoints = fusion.get("breakpoints")
            if not isinstance(breakpoints, list):
                breakpoints = []
            status = []
            if fusion.get("interesting"):
                status.append("report")
            if fusion.get("fp"):
                status.append("false positive")
            if fusion.get("irrelevant"):
                status.append("irrelevant")

            rows.append(
                RnaFusionExportRow(
                    gene_1=safe_text(genes[0] if len(genes) > 0 else ""),
                    gene_2=safe_text(genes[1] if len(genes) > 1 else ""),
                    effect=safe_text(selected_call.get("effect") or fusion.get("frame")),
                    spanning_pairs=safe_text(
                        selected_call.get("spanpairs")
                        or fusion.get("supporting_reads", {}).get("span")
                        or ""
                    ),
                    unique_spanning_reads=safe_text(
                        selected_call.get("spanreads")
                        or fusion.get("supporting_reads", {}).get("split")
                        or ""
                    ),
                    breakpoint_1=safe_text(
                        selected_call.get("breakpoint1")
                        or (breakpoints[0] if len(breakpoints) > 0 else "")
                    ),
                    breakpoint_2=safe_text(
                        selected_call.get("breakpoint2")
                        or (breakpoints[1] if len(breakpoints) > 1 else "")
                    ),
                    tier=safe_text(tier if tier not in {None, 999} else ""),
                    callers=join_tokens(
                        [call.get("caller") for call in calls if call.get("caller")]
                        or fusion.get("callers")
                        or selected_call.get("caller")
                    ),
                    description=safe_text(selected_call.get("desc") or fusion.get("desc")),
                    status=join_tokens(status),
                    false_positive=yes_no(fusion.get("fp")),
                    irrelevant=yes_no(fusion.get("irrelevant")),
                    interesting=yes_no(fusion.get("interesting")),
                    latest_comment=safe_text(latest_comment.get("text")),
                    latest_comment_author=safe_text(latest_comment.get("author")),
                    latest_comment_time=safe_text(latest_comment.get("time_created")),
                )
            )
        return rows

    @staticmethod
    def export_rows_to_csv(rows: list[RnaFusionExportRow]) -> str:
        """Serialize fusion export rows as CSV text."""
        return export_rows_to_csv(rows)

    @staticmethod
    def _fusion_genes(fusion: dict[str, Any]) -> list[str]:
        """Return a stable two-gene fusion label from known payload shapes."""
        if fusion.get("gene1") or fusion.get("gene2"):
            return [safe_text(fusion.get("gene1")), safe_text(fusion.get("gene2"))]
        genes = fusion.get("genes")
        if isinstance(genes, str):
            separator = "^" if "^" in genes else "--" if "--" in genes else "-"
            return [part.strip() for part in genes.split(separator) if part.strip()]
        if isinstance(genes, list):
            return [safe_text(gene) for gene in genes if safe_text(gene)]
        fusion_name = fusion.get("fusion_name")
        if isinstance(fusion_name, str):
            return [part.strip() for part in fusion_name.split("--") if part.strip()]
        return []

    def set_fusion_flag(self, *, fusion_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single fusion."""
        if flag == "false_positive":
            if apply:
                self.fusion_repository.mark_false_positive_fusion(fusion_id)
            else:
                self.fusion_repository.unmark_false_positive_fusion(fusion_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def select_fusion_call(self, *, fusion_id: str, callidx: str, num_calls: str) -> None:
        """Persist the selected call index for a fusion."""
        self.fusion_repository.pick_fusion(fusion_id, callidx, num_calls)

    def set_fusion_comment_hidden(self, *, fusion_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a fusion comment."""
        if hidden:
            self.fusion_repository.hide_fus_comment(fusion_id, comment_id)
            return
        self.fusion_repository.unhide_fus_comment(fusion_id, comment_id)

    def set_fusion_bulk_flag(
        self, *, fusion_ids: list[str], apply: bool, flag: str
    ) -> OperationResult:
        """Apply or remove a bulk boolean flag on fusions."""
        if not fusion_ids:
            return OperationResult.empty()
        if flag == "false_positive":
            return self.fusion_repository.mark_false_positive_bulk(fusion_ids, apply)
        if flag == "irrelevant":
            return self.fusion_repository.mark_irrelevant_bulk(fusion_ids, apply)
        raise ValueError(f"Unsupported flag: {flag}")
