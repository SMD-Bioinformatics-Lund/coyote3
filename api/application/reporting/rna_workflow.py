"""Common RNA workflow orchestration for reporting and fusion routes."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from api.application.interpretation.annotation_enrichment import add_alt_class
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.application.reporting.persistence import (
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from api.application.reporting.persistence import (
    prepare_report_output as prepare_shared_report_output,
)
from api.domain.common.assay_filters import (
    format_filters_from_form,
    get_sample_effective_genes,
    has_sample_gene_restriction,
    merge_sample_settings_with_assay_config,
)
from api.domain.common.reporting import TIER_DESC, TIER_SHORT_DESC, get_report_header, utc_now
from api.domain.common.sample_filters import sample_filter_section
from api.domain.core.reporting.report_paths import build_report_file_location
from api.domain.core.rna.fusion_query_builder import build_fusion_query
from api.domain.core.rna.helpers import (
    create_fusioncallers,
    create_fusioneffectlist,
    get_fusion_callers,
    get_selected_fusioncall,
)
from api.domain.core.workflows.contracts import (
    validate_report_inputs,
    validate_rna_filter_inputs,
)
from api.domain.core.workflows.filter_normalization import normalize_rna_filter_keys

util = SimpleNamespace(
    common=SimpleNamespace(
        merge_sample_settings_with_assay_config=merge_sample_settings_with_assay_config,
        format_filters_from_form=format_filters_from_form,
        get_sample_effective_genes=get_sample_effective_genes,
    )
)


class RNAWorkflowService:
    """Coordinate common RNA workflow steps."""

    @classmethod
    def from_store(cls, store) -> "RNAWorkflowService":
        """Build the workflow service from the runtime store."""
        return cls(
            sample_repository=store.sample_repository,
            gene_list_repository=store.gene_list_repository,
            rna_expression_repository=store.rna_expression_repository,
            rna_classification_repository=store.rna_classification_repository,
            rna_quality_repository=store.rna_quality_repository,
            fusion_repository=store.fusion_repository,
            annotation_repository=store.annotation_repository,
            assay_panel_repository=store.assay_panel_repository,
            reported_variant_repository=store.reported_variant_repository,
            report_repository=store.report_repository,
            clinical_rule_service=ClinicalRuleService.from_store(store),
        )

    def __init__(
        self,
        *,
        sample_repository,
        gene_list_repository,
        rna_expression_repository,
        rna_classification_repository,
        rna_quality_repository,
        fusion_repository,
        annotation_repository,
        assay_panel_repository,
        reported_variant_repository,
        report_repository,
        clinical_rule_service=None,
    ) -> None:
        """Create the workflow service with explicit injected repositories."""
        self.sample_repository = sample_repository
        self.gene_list_repository = gene_list_repository
        self.rna_expression_repository = rna_expression_repository
        self.rna_classification_repository = rna_classification_repository
        self.rna_quality_repository = rna_quality_repository
        self.fusion_repository = fusion_repository
        self.annotation_repository = annotation_repository
        self.assay_panel_repository = assay_panel_repository
        self.reported_variant_repository = reported_variant_repository
        self.report_repository = report_repository
        self.clinical_rule_service = clinical_rule_service

    def next_report_num(self, sample_id: str) -> int:
        """Return the next sequential report number for a sample."""
        return self.report_repository.next_report_num(sample_id)

    @staticmethod
    def merge_and_normalize_sample_filters(
        sample: dict, assay_config: dict, sample_id: str, logger
    ) -> tuple[dict, dict]:
        """Merge assay defaults into the sample and normalize RNA filters."""
        if sample.get("filters") is None:
            sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
        sample_filters = normalize_rna_filter_keys(
            sample_filter_section(
                sample.get("filters"),
                "fusion",
                omics_layer="rna",
                analysis_intents=sample.get("analysis_intents"),
            )
        )
        validate_rna_filter_inputs(logger, sample.get("name", sample_id), sample_filters)
        return sample, sample_filters

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
        filters_from_form["fusionlists"] = request_form.getlist("fusionlists")
        filters_from_form["fusion_callers"] = create_fusioncallers(
            filters_from_form.get("fusion_callers", [])
        )
        filters_from_form["fusion_effects"] = create_fusioneffectlist(
            filters_from_form.get("fusion_effects", [])
        )
        existing_fusion_filters = sample_filter_section(
            sample.get("filters"), "fusion", omics_layer="rna"
        )
        if existing_fusion_filters.get("adhoc_genes"):
            filters_from_form["adhoc_genes"] = existing_fusion_filters.get("adhoc_genes")
        self.sample_repository.update_sample_filters(
            _id, {"somatic": {"fusion": filters_from_form}}
        )

        updated_sample = self.sample_repository.get_sample(_id)
        updated_filters = normalize_rna_filter_keys(
            sample_filter_section(updated_sample.get("filters"), "fusion", omics_layer="rna")
        )
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
        fusion_descriptions = sorted(
            {
                str(value).strip().lower()
                for value in sample_filters.get("fusion_descriptions", [])
                if str(value).strip()
            }
        )
        checked_fusionlists = sample_filters.get("fusionlists", [])
        checked_fusionlists_genes_dict = self.gene_list_repository.get_isgl_by_ids(
            checked_fusionlists
        )

        genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
            sample, assay_panel_doc, checked_fusionlists_genes_dict, target="fusion"
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
            "fusion_descriptions": fusion_descriptions,
            "checked_fusionlists": checked_fusionlists,
            "genes_covered_in_panel": genes_covered_in_panel,
            "filter_genes": filter_genes,
            "restrict_to_genes": has_sample_gene_restriction(
                {
                    **sample,
                    "omics_layer": "rna",
                    "filters": {"somatic": {"fusion": sample_filters}},
                },
                assay_panel_doc,
                target="fusion",
            ),
            "fusion_effect_form_keys": fusion_effect_form_keys,
        }

    @staticmethod
    def build_fusion_list_query(
        assay_group: str,
        sample_id: str,
        sample_filters: dict,
        filter_context: dict,
        *,
        asp_id: str,
        subpanel_id: str,
        intent: str = "somatic",
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
                "fusion_descriptions": filter_context["fusion_descriptions"],
                "checked_fusionlists": filter_context["checked_fusionlists"],
                "filter_genes": filter_context["filter_genes"],
                "restrict_to_genes": filter_context["restrict_to_genes"],
                "asp_id": asp_id,
                "subpanel_id": subpanel_id,
                "intent": intent,
            },
        )

    def attach_rna_analysis_sections(self, sample: dict) -> dict:
        """Attach RNA expression, classification, and QC sections to the sample."""
        sample["expr"] = self.rna_expression_repository.get_rna_expression(str(sample["_id"]))
        sample["classification"] = self.rna_classification_repository.get_rna_classification(
            str(sample["_id"])
        )
        sample["QC_metrics"] = self.rna_quality_repository.get_rna_qc(str(sample["_id"]))
        return sample

    def build_show_fusion_context(
        self,
        fusion: dict,
        assay_group: str,
        subpanel: str,
    ) -> dict:
        """Build annotation and classification context for a fusion detail view."""
        in_other = self.fusion_repository.get_fusion_in_other_samples(fusion)
        selected_fusion_call = get_selected_fusioncall(fusion)
        (
            annotations,
            latest_classification,
            other_classifications,
            annotations_interesting,
        ) = self.annotation_repository.get_global_annotations(
            selected_fusion_call, assay_group, subpanel
        )

        if not latest_classification or latest_classification.get("class") == 999:
            fusion = add_alt_class(
                fusion,
                assay_group,
                subpanel,
                annotation_repository=self.annotation_repository,
            )
        else:
            fusion["additional_classifications"] = None

        has_hidden_comments = self.fusion_repository.hidden_fusion_comments(str(fusion.get("_id")))
        assay_group_mappings = self.assay_panel_repository.get_asp_group_mappings()
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
        rule_provenance: dict | None = None,
    ) -> tuple[str, str]:
        """
        Persist RNA report artifacts via common reporting pipeline.
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
            rule_provenance=rule_provenance,
            sample_repository=self.sample_repository,
            reported_variant_repository=self.reported_variant_repository,
        )

    @staticmethod
    def _selected_report_call(fusion: dict) -> dict:
        """Return the single selected call required by the RNA report contract."""
        selected_calls = [
            call
            for call in fusion.get("calls", [])
            if isinstance(call, dict) and call.get("selected") == 1
        ]
        if len(selected_calls) != 1:
            fusion_id = fusion.get("_id") or f"{fusion.get('gene1')}::{fusion.get('gene2')}"
            raise ValueError(
                f"Fusion '{fusion_id}' must contain exactly one selected call; "
                f"found {len(selected_calls)}."
            )
        return selected_calls[0]

    @classmethod
    def _validate_reportable_fusion(cls, fusion: dict) -> None:
        """Validate canonical fields consumed by RNA report rendering and snapshots."""
        missing = [field for field in ("gene1", "gene2") if not fusion.get(field)]
        if missing:
            fusion_id = fusion.get("_id") or "unknown"
            raise ValueError(
                f"Fusion '{fusion_id}' is missing required report field(s): {', '.join(missing)}."
            )
        cls._selected_report_call(fusion)

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
            if fus.get("blacklist") or fus.get("blacklisted") or tier in (None, 999, 4):
                continue

            RNAWorkflowService._validate_reportable_fusion(fus)
            calls = fus["calls"]
            selected = RNAWorkflowService._selected_report_call(fus)
            gene1 = fus["gene1"]
            gene2 = fus["gene2"]

            bp1 = selected.get("breakpoint1", "")
            bp2 = selected.get("breakpoint2", "")
            simple_id = f"{gene1}::{gene2}::{bp1}::{bp2}"
            annotations = fus.get("global_annotations") or []
            visible_annotations = [
                annotation
                for annotation in annotations
                if isinstance(annotation, dict)
                and annotation.get("text")
                and not annotation.get("hidden")
            ]
            latest_annotation = max(
                visible_annotations,
                key=lambda annotation: str(
                    annotation.get("time_created") or annotation.get("created_on") or ""
                ),
                default={},
            )

            rows.append(
                {
                    "var_oid": fus.get("_id"),
                    "simple_id": simple_id,
                    "tier": tier,
                    "gene": f"{gene1}-{gene2}",
                    "fusion": f"{gene1}::{gene2}",
                    "gene_1": gene1,
                    "gene_2": gene2,
                    "breakpoint_1": bp1,
                    "breakpoint_2": bp2,
                    "effect": selected.get("effect"),
                    "spanning_pairs": selected.get("spanpairs"),
                    "spanning_reads": selected.get("spanreads"),
                    "longest_anchor": selected.get("longestanchor"),
                    "callers": [
                        call.get("caller")
                        for call in calls
                        if isinstance(call, dict) and call.get("caller")
                    ],
                    "created_on": created_on,
                    "annotation_oid": cls.get("_id"),
                    "classification": tier,
                    "text": latest_annotation.get("text", ""),
                }
            )
        return rows

    def build_report_payload(
        self,
        sample: dict,
        assay_config: dict,
        save: int,
        include_snapshot: bool,
    ):
        """
        Build RNA report template context and optional snapshot rows through cross-domain workflow service.
        """
        assay = str(sample.get("asp_id") or "").strip()
        if not assay:
            raise ValueError("RNA report input is missing the canonical sample asp_id.")
        reporting_config = assay_config["reporting"]
        fusion_query = {"SAMPLE_ID": str(sample["_id"])}
        fusions = list(self.fusion_repository.get_sample_fusions(fusion_query) or [])

        for fus_idx, fusion in enumerate(fusions):
            (
                fusions[fus_idx]["global_annotations"],
                fusions[fus_idx]["classification"],
            ) = self.fusion_repository.get_fusion_annotations(fusion)

        report_header = get_report_header(
            str(assay_config["asp_group"]),
            sample,
            reporting_config["report_header"],
        )
        report_date = datetime.now().date()
        reportable_fusions = [
            fusion
            for fusion in fusions
            if not fusion.get("blacklist")
            and not fusion.get("blacklisted")
            and not fusion.get("fp")
            and not fusion.get("irrelevant")
            and (fusion.get("classification") or {}).get("class") not in (None, 4, 999)
        ]
        for fusion in reportable_fusions:
            self._validate_reportable_fusion(fusion)
        fusion_filters = sample_filter_section(sample.get("filters"), "fusion", omics_layer="rna")
        selected_list_ids = list(fusion_filters.get("fusionlists", []) or [])
        selected_list_docs = self.gene_list_repository.get_isgl_by_ids(selected_list_ids)
        applied_gene_lists = [
            {**document, "isgl_id": isgl_id, "selected_for": ["fusion"]}
            for isgl_id, document in selected_list_docs.items()
        ]
        assay_panel = self.assay_panel_repository.get_asp(str(sample.get("asp_id") or "")) or {}
        prepared_rule_context = prepare_report_context(
            sample=sample,
            asp=assay_panel,
            aspc=assay_config,
            analyte="rna",
            applied_gene_lists=applied_gene_lists,
            report_sections_data={"fusions": reportable_fusions},
        )
        clinical_rule_evaluation = (
            self.clinical_rule_service.evaluate(
                aspc=assay_config,
                context=prepared_rule_context,
            )
            if self.clinical_rule_service is not None
            else None
        )
        latest_sample_comment = self.sample_repository.get_latest_sample_comment(
            str(sample.get("_id") or "")
        )

        template_context = {
            "asp_id": assay,
            "assay_config": assay_config,
            "fusions": reportable_fusions,
            "report_header": report_header,
            "sample": sample,
            "class_desc": TIER_DESC,
            "class_desc_short": TIER_SHORT_DESC,
            "report_date": report_date,
            "save": save,
            "latest_sample_comment_text": str((latest_sample_comment or {}).get("text") or ""),
            "clinical_rule_evaluation": (
                clinical_rule_evaluation.model_dump(mode="json")
                if clinical_rule_evaluation
                else None
            ),
        }

        if not include_snapshot:
            return "report_fusion.html", template_context, []
        return (
            "report_fusion.html",
            template_context,
            RNAWorkflowService._build_snapshot_rows(reportable_fusions),
        )
