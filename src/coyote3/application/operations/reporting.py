"""Application-owned report preview and save orchestration for local callers."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from coyote3.application.operations.clinical import _sample
from coyote3.application.operations.models import (
    Download,
    FindingPage,
    ReportPreview,
    ReportTrial,
    SavedReport,
)
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.reporting.dna_workflow import DNAWorkflowService
    from coyote3.application.reporting.report_library import ReportLibraryService
    from coyote3.application.reporting.rna_workflow import RNAWorkflowService

Analyte = Literal["dna", "rna"]


class ReportingServices:
    """Explicit configuration, rendering and persistence capabilities for reports."""

    def __init__(
        self,
        *,
        workflow: Callable[[Analyte], DNAWorkflowService | RNAWorkflowService],
        configuration: Callable[[dict[str, Any]], dict[str, Any]],
        render_html: Callable[..., str],
        organization_name: str,
        reports_base_path: str,
        logger: Any,
        library: Callable[[], ReportLibraryService],
        render_pdf: Callable[[str], bytes],
        render_trial_html: Callable[..., str] | None = None,
        presentation: Callable[[], ReportPresentation] | None = None,
    ) -> None:
        """Bind report workflows and host-owned rendering and artifact capabilities.

        Args:
            workflow: Selects the existing DNA or RNA preparation/persistence workflow.
            configuration: Resolves the sample's applied assay configuration.
            render_html: Renders the prepared template and context without persisting a report.
            organization_name: Center name used by established report presentation.
            reports_base_path: Host report artifact root; existing path rules still apply.
            logger: Records report preparation and persistence diagnostics.
            library: Supplies the current actor's report library and pagination.
            render_pdf: Converts rendered HTML into PDF bytes for preview downloads.
            render_trial_html: Optional host renderer accepting the same prepared inputs
                as render_html. None selects the packaged modern layout directly.
            presentation: Supplies modern wording before preview fingerprinting. None
                retains defaults; the SDK does not read host configuration files.
        """
        self.workflow, self.configuration, self.render_html = workflow, configuration, render_html
        self.organization_name, self.reports_base_path = organization_name, reports_base_path
        self.logger = logger
        self.library, self.render_pdf = library, render_pdf
        self.render_trial_html = render_trial_html
        self.presentation = presentation or ReportPresentation


class Reports:
    """Render and save sample reports under current authorization and preview consistency."""

    def __init__(self, runtime: ApplicationRuntime, services: ReportingServices) -> None:
        """Bind authenticated execution and report infrastructure capabilities."""
        self._runtime, self._services = runtime, services

    def try_new(self, sample_id: str, analyte: Analyte) -> ReportTrial:
        """Render an alternate HTML/PDF pair without allocating or saving a report.

        Args:
            sample_id: Sample name or identifier, checked against current clinical access.
            analyte: DNA or RNA workflow supplying the established report content.

        Returns:
            Matching HTML and PDF bytes prepared from the same clinical inputs.

        Raises:
            AppError: Current identity lacks report:preview or sample access.
            ValueError: The analyte is invalid.

        Notes:
            Access auditing remains active. No report number, output path, persistence
            service or saved-report notification is used.
        """
        if analyte not in {"dna", "rna"}:
            raise ValueError("Report analyte must be dna or rna")

        def render(actor: Any, record: dict[str, Any] | None) -> ReportTrial:
            """Prepare clinical content once and render both temporary representations."""
            template, context, rows, _ = self._build(
                _sample(record), analyte, save=False, include_snapshot=True
            )
            renderer = self._services.render_trial_html or self._services.render_html
            options = {} if self._services.render_trial_html else {"layout": "modern"}
            html = renderer(
                organization_name=self._services.organization_name,
                generated_by=actor.fullname or actor.username,
                template_name=template,
                template_context=context,
                snapshot_rows=rows,
                analyte=analyte,
                preview=True,
                **options,
            )
            return ReportTrial(
                html=html,
                pdf=self._services.render_pdf(html),
                filename=f"coyote3_{analyte}_report_trial",
                snapshot_count=len(rows),
            )

        return self._runtime.execute(
            "reports.try_new", ("report:preview",), render, sample_id=sample_id
        )

    def list(self, *, search: str = "", page: int = 1, per_page: int = 30) -> FindingPage:
        """List saved report summaries within the actor's current assay and environment scope.

        Args:
            search: Sample or report search text; an empty string applies no text filter.
            page: One-based page number.
            per_page: Maximum summaries per page, between 1 and 200.

        Returns:
            Report summaries with pagination, without generating any report artifacts.

        Raises:
            ValueError: Pagination is outside its supported bounds.
            AppError: The current actor lacks report:view.
        """
        if page < 1 or not 1 <= per_page <= 200:
            raise ValueError("Page must be positive and page size must be between 1 and 200")

        def read(actor: Any, sample: dict[str, Any] | None) -> FindingPage:
            """Use the report library's scoped query and immutable finding counts."""
            payload = self._services.library().list_payload(
                user=actor, search=search, page=page, per_page=per_page
            )
            return FindingPage(
                items=payload["reports"],
                pagination={key: payload[key] for key in ("total", "page", "per_page", "has_next")},
            )

        return self._runtime.execute("reports.list", ("report:view",), read)

    def preview_pdf(
        self, sample_id: str, analyte: Analyte, *, include_snapshot: bool = True
    ) -> Download:
        """Generate a PDF of the current authorized preview without saving report records.

        Args:
            sample_id: Sample name or identifier, checked using the current session and scope.
            analyte: DNA or RNA report modality matching the sample.
            include_snapshot: Include finding snapshot context when True.

        Returns:
            PDF bytes and the established sample-based download filename.
        """
        preview = self.preview(sample_id, analyte, include_snapshot=include_snapshot)
        return Download(
            filename=f"{preview.sample.get('name') or sample_id}_{analyte}_preview.pdf",
            content=self._services.render_pdf(preview.html),
            media_type="application/pdf",
        )

    def _build(
        self, sample: dict[str, Any], analyte: Analyte, *, save: bool, include_snapshot: bool
    ) -> tuple[str, dict[str, Any], builtins.list[dict[str, Any]], dict[str, Any]]:
        """Validate modality and build the existing clinical report context and snapshots."""
        category = str(sample.get("asp_category") or "").lower()
        if category in {"dna", "rna"} and category != analyte:
            sample_name = str(sample.get("name") or sample.get("case_id") or "sample")
            raise api_error(
                422,
                "Report type does not match sample modality",
                f"Sample '{sample_name}' has omics layer '{category}'. "
                f"Use the {category.upper()} report endpoint for this sample.",
                category="validation",
            )
        config = self._services.configuration(sample)
        if not config:
            raise api_error(
                422,
                "ASPC could not be resolved for the sample",
                f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                "configuration during report generation.",
                category="setup",
            )
        workflow = self._services.workflow(analyte)
        workflow.validate_report_inputs(self._services.logger, sample, config)
        from coyote3.application.query_rules.compilation import (
            capture_query_policies,
            query_policies_hash,
        )
        from coyote3.application.reporting.clinical_rules.resolution import capture_clinical_rules

        try:
            with capture_query_policies() as policies, capture_clinical_rules() as rules:
                template, context, rows = workflow.build_report_payload(
                    sample=sample,
                    assay_config=config,
                    save=int(save),
                    include_snapshot=include_snapshot,
                )
                resolved = {key: value.model_dump(mode="json") for key, value in policies.items()}
                context["query_policy_resolution"] = {
                    "policies": resolved,
                    "content_hash": query_policies_hash(resolved),
                }
                selected_rules = next(iter(rules.values()), {})
                context["clinical_rule_resolution"] = selected_rules.get("rule_set")
                context["clinical_rule_sources"] = selected_rules
        except (KeyError, ValueError) as exc:
            raise api_error(
                422,
                f"{analyte.upper()} report data does not satisfy the reporting contract",
                str(exc),
                category="validation",
            ) from exc
        release = (context.get("assay_config") or {}).get("template_release") or {}
        if str(release.get("template_name") or template).startswith("modern/"):
            context["report_presentation"] = self._services.presentation().model_dump(mode="json")
        return template, context, rows or [], config

    def preview(
        self,
        sample_id: str,
        analyte: Analyte,
        *,
        include_snapshot: bool = False,
        save_context: bool = False,
    ) -> ReportPreview:
        """Render current report inputs with the fingerprint required by save.

        Args:
            sample_id: Sample name or identifier, reloaded under current sample scope.
            analyte: DNA or RNA modality matching the sample.
            include_snapshot: Include immutable finding rows when True.
            save_context: Render the save presentation without persisting artifacts.

        Returns:
            HTML, clinical context, optional finding rows and review fingerprint.
        """
        if analyte not in {"dna", "rna"}:
            raise ValueError("Report analyte must be dna or rna")

        def read(actor: Any, record: dict[str, Any] | None) -> ReportPreview:
            """Build and render the authorized sample without persisting report artifacts."""
            from coyote3.application.reporting.preview_consistency import preview_fingerprint

            template, context, rows, _ = self._build(
                _sample(record), analyte, save=save_context, include_snapshot=include_snapshot
            )
            fingerprint = preview_fingerprint(template, context)
            html = self._services.render_html(
                organization_name=self._services.organization_name,
                generated_by=actor.fullname or actor.username,
                template_name=template,
                template_context=context,
                snapshot_rows=rows,
                analyte=analyte,
                preview=not save_context,
            )
            return ReportPreview(
                template=template,
                context=context,
                html=html,
                snapshot_rows=rows if include_snapshot else [],
                fingerprint=fingerprint,
                sample=_sample(record),
                snapshot_count=len(rows),
            )

        return self._runtime.execute(
            "reports.preview", ("report:preview",), read, sample_id=sample_id
        )

    def save(self, sample_id: str, analyte: Analyte, *, fingerprint: str) -> SavedReport:
        """Save a reviewed report, rejecting changed inputs before creating artifacts.

        Args:
            sample_id: Sample name or identifier, reloaded under current sample scope.
            analyte: DNA or RNA modality matching the sample.
            fingerprint: Fingerprint returned by the reviewed preview.

        Returns:
            Report identity, artifact locations and finding snapshot count.

        Raises:
            AppError: Access is denied, report inputs are invalid or the preview is stale.
        """
        if analyte not in {"dna", "rna"}:
            raise ValueError("Report analyte must be dna or rna")

        def write(actor: Any, record: dict[str, Any] | None) -> SavedReport:
            """Validate the reviewed fingerprint before number allocation or filesystem writes."""
            from coyote3.application.reporting.preview_consistency import require_current_preview
            from coyote3.application.reporting.resolution_receipt import report_resolution_receipt

            sample = _sample(record)
            template, context, rows, config = self._build(
                sample, analyte, save=True, include_snapshot=True
            )
            require_current_preview(fingerprint, template, context)
            workflow = self._services.workflow(analyte)
            number = workflow.next_report_num(str(sample["_id"]))
            report_id, path, filename = workflow.build_report_location(
                sample, config, self._services.reports_base_path
            )
            workflow.prepare_report_output(path, filename, logger=self._services.logger)
            if isinstance(context.get("sample"), dict):
                context["sample"]["report_num"] = max(int(number) - 1, 0)
            html = self._services.render_html(
                organization_name=self._services.organization_name,
                generated_by=actor.fullname or actor.username,
                template_name=template,
                template_context=context,
                snapshot_rows=rows,
                analyte=analyte,
                preview=False,
            )
            evaluation = context.get("clinical_rule_evaluation")
            provenance = None
            if isinstance(evaluation, dict) and isinstance(evaluation.get("source"), dict):
                provenance = {
                    "source": evaluation["source"],
                    "matched_rule_ids": list(
                        dict.fromkeys(
                            str(item["rule_id"])
                            for item in evaluation.get("trace", [])
                            if isinstance(item, dict)
                            and item.get("matched")
                            and item.get("rule_id")
                        )
                    ),
                }
            storage_id, pdf = workflow.persist_report(
                sample_id=sample_id,
                sample=sample,
                report_num=number,
                report_id=report_id,
                report_file=filename,
                html=html,
                snapshot_rows=rows,
                created_by=actor.username,
                rule_provenance=provenance,
                resolution_snapshot=report_resolution_receipt(template, context),
            )
            return SavedReport(
                id=report_id,
                storage_id=str(storage_id),
                file=filename,
                pdf_file=pdf,
                snapshot_count=len(rows),
                sample=sample,
            )

        return self._runtime.execute("reports.save", ("report:create",), write, sample_id=sample_id)
