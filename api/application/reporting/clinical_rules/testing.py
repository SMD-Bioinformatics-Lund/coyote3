"""Read-only testing of governed rule versions against existing sample data."""

from __future__ import annotations

from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.reporting.clinical_rules.service import rendered_summary
from api.application.reporting.dna_workflow import DNAWorkflowService
from api.application.reporting.rna_workflow import RNAWorkflowService
from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluation, ClinicalRuleSetDoc
from api.domain.common.errors import api_error


class ClinicalRuleTestingService:
    """Search compatible samples and build non-persisting report-text previews."""

    @classmethod
    def from_store(cls, store: Any) -> "ClinicalRuleTestingService":
        return cls(
            rule_repository=store.clinical_rule_set_repository,
            sample_repository=store.sample_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            dna_workflow=DNAWorkflowService.from_store(store),
            rna_workflow=RNAWorkflowService.from_store(store),
        )

    def __init__(
        self,
        *,
        rule_repository: Any,
        sample_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: Any,
        dna_workflow: Any,
        rna_workflow: Any,
    ) -> None:
        self.rule_repository = rule_repository
        self.sample_repository = sample_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.dna_workflow = dna_workflow
        self.rna_workflow = rna_workflow

    def _rule_set(self, document_id: str) -> ClinicalRuleSetDoc:
        document = self.rule_repository.get(document_id)
        if document is None:
            raise api_error(404, "Clinical rule-set version was not found")
        return ClinicalRuleSetDoc.model_validate(document)

    def search_samples(
        self,
        *,
        document_id: str,
        search: str,
        match_subpanel: bool,
        allowed_asp_ids: list[str] | None,
        allowed_environments: list[str] | None,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        rule_set = self._rule_set(document_id)
        asp_id = rule_set.scope.asp_id
        if allowed_asp_ids is not None and asp_id not in set(allowed_asp_ids):
            raise api_error(403, "Clinical rule-set assay is outside your assigned scope")
        rows, total = self.sample_repository.search_samples_for_admin(
            asp_ids=[asp_id],
            environments=allowed_environments,
            subpanel_id=rule_set.scope.subpanel_id if match_subpanel else None,
            search_str=search,
            page=page,
            per_page=per_page,
            ready_only=True,
        )
        return {
            "items": [
                {
                    "id": str(row.get("_id")),
                    "name": str(row.get("name") or row.get("case_id") or row.get("_id")),
                    "asp_id": row.get("asp_id"),
                    "subpanel_id": row.get("subpanel_id") or "base",
                    "environment": row.get("environment"),
                    "omics_layer": row.get("omics_layer"),
                }
                for row in rows
            ],
            "page": page,
            "per_page": per_page,
            "total": total,
        }

    def preview(
        self,
        *,
        document_id: str,
        sample: dict[str, Any],
        include_condition_trace: bool = False,
    ) -> dict[str, Any]:
        rule_set = self._rule_set(document_id)
        if str(sample.get("asp_id") or "") != rule_set.scope.asp_id:
            raise api_error(422, "Sample assay does not match the clinical rule set")
        assay_config = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )
        workflow = self.dna_workflow if rule_set.scope.analyte == "dna" else self.rna_workflow
        try:
            _, template_context, _ = workflow.build_report_payload(
                sample=sample,
                assay_config=assay_config,
                save=0,
                include_snapshot=False,
                clinical_rule_override=rule_set,
                clinical_rule_only=True,
                clinical_rule_condition_trace=include_condition_trace,
            )
        except (KeyError, ValueError) as exc:
            raise api_error(
                422, "Sample data does not satisfy the reporting contract", str(exc)
            ) from exc
        evaluation = template_context.get("clinical_rule_evaluation")
        if not isinstance(evaluation, dict):
            raise api_error(422, "Clinical rule evaluation did not produce a preview")
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name") or sample.get("case_id"),
                "asp_id": sample.get("asp_id"),
                "subpanel_id": sample.get("subpanel_id") or "base",
                "environment": sample.get("environment"),
            },
            "rule_set": {
                "id": str(rule_set.id_),
                "rule_set_id": rule_set.rule_set_id,
                "content_version": rule_set.content_version,
                "status": rule_set.status.value,
            },
            "summary": rendered_summary(ClinicalRuleEvaluation.model_validate(evaluation)),
            "evaluation": evaluation,
            "persisted": False,
        }
