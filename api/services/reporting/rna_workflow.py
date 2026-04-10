"""Shared RNA workflow orchestration for reporting and fusion routes."""

from copy import deepcopy
from datetime import datetime
from typing import Any

from api.common.utility import utc_now
from api.core.reporting.report_paths import build_report_file_location
from api.core.rna.fusion_query_builder import build_fusion_query
from api.core.rna.helpers import (
    create_fusioncallers,
    create_fusioneffectlist,
    get_fusion_callers,
    get_selected_fusioncall,
)
from api.core.workflows.contracts import (
    validate_report_inputs,
    validate_rna_filter_inputs,
)
from api.core.workflows.filter_normalization import normalize_rna_filter_keys
from api.extensions import util
from api.runtime_state import app
from api.services.interpretation.annotation_enrichment import add_alt_class
from api.services.reporting.persistence import (
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from api.services.reporting.persistence import (
    prepare_report_output as prepare_shared_report_output,
)


class RNAWorkflowService:
    """Coordinate shared RNA workflow steps."""

    @classmethod
    def from_store(cls, store) -> "RNAWorkflowService":
        """Build the workflow service from the shared store."""
        return cls(
            sample_handler=store.sample_handler,
            gene_list_handler=store.gene_list_handler,
            rna_expression_handler=store.rna_expression_handler,
            rna_classification_handler=store.rna_classification_handler,
            rna_quality_handler=store.rna_quality_handler,
            fusion_handler=store.fusion_handler,
            annotation_handler=store.annotation_handler,
            assay_panel_handler=store.assay_panel_handler,
            reported_variant_handler=store.reported_variant_handler,
        )

    def __init__(
        self,
        *,
        sample_handler,
        gene_list_handler,
        rna_expression_handler,
        rna_classification_handler,
        rna_quality_handler,
        fusion_handler,
        annotation_handler,
        assay_panel_handler,
        reported_variant_handler,
    ) -> None:
        """Create the workflow service with explicit injected handlers."""
        self.sample_handler = sample_handler
        self.gene_list_handler = gene_list_handler
        self.rna_expression_handler = rna_expression_handler
        self.rna_classification_handler = rna_classification_handler
        self.rna_quality_handler = rna_quality_handler
        self.fusion_handler = fusion_handler
        self.annotation_handler = annotation_handler
        self.assay_panel_handler = assay_panel_handler
        self.reported_variant_handler = reported_variant_handler

    @staticmethod
    def merge_and_normalize_sample_filters(
        sample: dict, assay_config: dict, sample_id: str, logger
    ) -> tuple[dict, dict]:
        """Merge assay defaults into the sample and normalize RNA filters."""
        merged_sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
        sample_filters = normalize_rna_filter_keys(deepcopy(merged_sample.get("filters", {})))
        validate_rna_filter_inputs(logger, merged_sample.get("name", sample_id), sample_filters)
        return merged_sample, sample_filters

    def persist_form_filters(
        self,
        sample: dict,
        form: Any,
        assay_config_schema: dict,
        request_form: Any,
    ) -> tuple[dict, dict]:
        """Persist normalized RNA form filters and return refreshed sample state."""
        _id = str(sample.get("_id"))
        filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
        filters_from_form["fusionlists"] = request_form.getlist("fusionlist_id")
        filters_from_form["fusion_callers"] = create_fusioncallers(
            filters_from_form.get("fusion_callers", [])
        )
        filters_from_form["fusion_effects"] = create_fusioneffectlist(
            filters_from_form.get("fusion_effects", [])
        )
        if sample.get("filters", {}).get("adhoc_genes"):
            filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
        self.sample_handler.update_sample_filters(_id, filters_from_form)

        updated_sample = self.sample_handler.get_sample(_id)
        updated_filters = normalize_rna_filter_keys(deepcopy(updated_sample.get("filters")))
        return updated_sample, updated_filters

    def compute_filter_context(
        self,
        sample: dict,
        sample_filters: dict,
        assay_panel_doc: dict,
    ) -> dict:
        """Compute the canonical filter context used by fusion-list routes."""
        fusion_effects = create_fusioneffectlist(sample_filters.get("fusion_effects", []))
        fusion_callers = create_fusioncallers(sample_filters.get("fusion_callers", []))
        checked_fusionlists = sample_filters.get("fusionlists", [])
        checked_fusionlists_genes_dict = self.gene_list_handler.get_isgl_by_ids(checked_fusionlists)

        sample_for_gene_filter = deepcopy(sample)
        sample_for_gene_filter.setdefault("filters", {})
        sample_for_gene_filter["filters"]["genelists"] = checked_fusionlists
        genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
            sample_for_gene_filter, assay_panel_doc, checked_fusionlists_genes_dict, target="fusion"
        )

        fusion_effect_form_keys = []
        for effect in fusion_effects:
            if effect == "in-frame":
                fusion_effect_form_keys.append("inframe")
            elif effect == "out-of-frame":
                fusion_effect_form_keys.append("outframe")

        return {
            "fusion_effects": fusion_effects,
            "fusion_callers": fusion_callers,
            "checked_fusionlists": checked_fusionlists,
            "genes_covered_in_panel": genes_covered_in_panel,
            "filter_genes": filter_genes,
            "fusion_effect_form_keys": fusion_effect_form_keys,
        }

    @staticmethod
    def build_fusion_list_query(
        assay_group: str,
        sample_id: str,
        sample_filters: dict,
        filter_context: dict,
    ) -> dict:
        """Build the fusion query from canonicalized filter state."""
        return build_fusion_query(
            assay_group,
            settings={
                "id": str(sample_id),
                "min_spanning_reads": sample_filters.get("min_spanning_reads", 0),
                "min_spanning_pairs": sample_filters.get("min_spanning_pairs", 0),
                "fusion_effects": filter_context["fusion_effects"],
                "fusion_callers": filter_context["fusion_callers"],
                "checked_fusionlists": filter_context["checked_fusionlists"],
                "filter_genes": filter_context["filter_genes"],
            },
        )

    def attach_rna_analysis_sections(self, sample: dict) -> dict:
        """Attach RNA expression, classification, and QC sections to the sample."""
        sample["expr"] = self.rna_expression_handler.get_rna_expression(str(sample["_id"]))
        sample["classification"] = self.rna_classification_handler.get_rna_classification(
            str(sample["_id"])
        )
        sample["QC_metrics"] = self.rna_quality_handler.get_rna_qc(str(sample["_id"]))
        return sample

    def build_show_fusion_context(
        self,
        fusion: dict,
        assay_group: str,
        subpanel: str,
    ) -> dict:
        """Build annotation and classification context for a fusion detail view."""
        in_other = self.fusion_handler.get_fusion_in_other_samples(fusion)
        selected_fusion_call = get_selected_fusioncall(fusion)
        (
            annotations,
            latest_classification,
            other_classifications,
            annotations_interesting,
        ) = self.annotation_handler.get_global_annotations(
            selected_fusion_call, assay_group, subpanel
        )

        if not latest_classification or latest_classification.get("class") == 999:
            fusion = add_alt_class(
                fusion,
                assay_group,
                subpanel,
                annotation_handler=self.annotation_handler,
            )
        else:
            fusion["additional_classifications"] = None

        has_hidden_comments = self.fusion_handler.hidden_fusion_comments(str(fusion.get("_id")))
        assay_group_mappings = self.assay_panel_handler.get_asp_group_mappings()
        fusion["fusion_callers"] = get_fusion_callers(fusion)

        return {
            "fusion": fusion,
            "in_other": in_other,
            "annotations": annotations,
            "latest_classification": latest_classification,
            "other_classifications": other_classifications,
            "annotations_interesting": annotations_interesting,
            "hidden_comments": has_hidden_comments,
            "assay_group_mappings": assay_group_mappings,
        }

    @staticmethod
    def validate_report_inputs(logger, sample: dict, assay_config: dict) -> None:
        """Validate RNA report prerequisites before building output."""
        validate_report_inputs(logger, sample, assay_config, analyte="rna")

    @staticmethod
    def build_report_location(
        sample: dict, assay_config: dict, reports_base_path: str
    ) -> tuple[str, str, str]:
        """Build report identifiers and output paths for RNA reports."""
        assay_group = assay_config.get("asp_group", "rna")
        return build_report_file_location(
            sample=sample,
            assay_config=assay_config,
            default_assay_group=assay_group,
            reports_base_path=reports_base_path,
        )

    @staticmethod
    def prepare_report_output(report_path: str, report_file: str, logger=None) -> None:
        """Prepare the RNA report output destination."""
        prepare_shared_report_output(report_path, report_file, logger=logger)

    def persist_report(
        self,
        *,
        sample_id: str,
        sample: dict,
        report_num: int,
        report_id: str,
        report_file: str,
        html: str,
        snapshot_rows: list | None,
        created_by: str,
    ) -> str:
        """
        Persist RNA report artifacts via shared reporting pipeline.
        """
        return persist_shared_report_and_snapshot(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
            sample_handler=self.sample_handler,
            reported_variant_handler=self.reported_variant_handler,
        )

    @staticmethod
    def _build_snapshot_rows(fusions: list[dict]) -> list[dict]:
        """
        Build snapshot rows for report persistence.
        """
        created_on = utc_now()
        rows = []

        for fus in fusions:
            cls = fus.get("classification") or {}
            tier = cls.get("class", 999)
            if fus.get("blacklist") or tier in (None, 999, 4):
                continue

            calls = fus.get("calls") or []
            selected = next((c for c in calls if c.get("selected") == 1), calls[0] if calls else {})

            gene1 = fus.get("gene1")
            gene2 = fus.get("gene2")
            if (
                (not gene1 or not gene2)
                and isinstance(fus.get("genes"), str)
                and "^" in fus.get("genes")
            ):
                _g = fus.get("genes").split("^")
                gene1 = gene1 or _g[0]
                gene2 = gene2 or (_g[1] if len(_g) > 1 else None)

            bp1 = selected.get("breakpoint1", "")
            bp2 = selected.get("breakpoint2", "")
            simple_id = f"{gene1 or 'NA'}::{gene2 or 'NA'}::{bp1}::{bp2}"

            rows.append(
                {
                    "var_oid": fus.get("_id"),
                    "simple_id": simple_id,
                    "tier": tier,
                    "gene": f"{gene1 or 'NA'}-{gene2 or 'NA'}",
                    "transcript": selected.get("transcript"),
                    "hgvsp": None,
                    "hgvsc": None,
                    "created_on": created_on,
                    "annotation_oid": cls.get("_id"),
                }
            )
        return rows

    def build_report_payload(
        self,
        sample: dict,
        save: int,
        include_snapshot: bool,
    ):
        """
        Build RNA report template context and optional snapshot rows through shared workflow service.
        """
        assay = util.common.get_assay_from_sample(sample)
        fusion_query = {"SAMPLE_ID": str(sample["_id"])}
        fusions = list(self.fusion_handler.get_sample_fusions(fusion_query) or [])

        for fus_idx, fusion in enumerate(fusions):
            (
                fusions[fus_idx]["global_annotations"],
                fusions[fus_idx]["classification"],
            ) = self.fusion_handler.get_fusion_annotations(fusion)

        class_desc = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC").values())
        class_desc_short = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT").values())
        analysis_desc = app.config.get("REPORT_CONFIG").get("ANALYSIS_DESCRIPTION", {}).get(assay)
        analysis_method = util.common.get_analysis_method(assay)
        report_header = util.common.get_report_header(assay, sample)
        report_date = datetime.now().date()

        template_context = {
            "assay": assay,
            "fusions": fusions,
            "report_header": report_header,
            "analysis_method": analysis_method,
            "analysis_desc": analysis_desc,
            "sample": sample,
            "class_desc": class_desc,
            "class_desc_short": class_desc_short,
            "report_date": report_date,
            "save": save,
        }

        if not include_snapshot:
            return "report_fusion.html", template_context, []
        return (
            "report_fusion.html",
            template_context,
            RNAWorkflowService._build_snapshot_rows(fusions),
        )
