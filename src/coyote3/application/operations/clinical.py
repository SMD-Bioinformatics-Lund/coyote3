"""Sample and finding resources for trusted in-process application callers."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal

from coyote3.application.common.analysis_query import AnalysisQuery
from coyote3.application.operations.models import CsvExport, FindingPage, FlagChange
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.biomarker.biomarker_lookup import BiomarkerService
    from coyote3.application.classification.tiering import ResourceClassificationService
    from coyote3.application.classification.variant_annotation import ResourceAnnotationService
    from coyote3.application.common.query_service import CommonQueryService
    from coyote3.application.dna.structural_variants import DnaStructuralService
    from coyote3.application.dna.variant_analysis import DnaService
    from coyote3.application.knowledgebase.public_variants import PublicVariantAnnotations
    from coyote3.application.operations.ports import RegisteredArtifacts
    from coyote3.application.resources.fields import ResourceFieldService
    from coyote3.application.rna.expression_analysis import RnaService
    from coyote3.application.sample.catalog import SampleCatalogService
    from coyote3.application.sample.coverage import CoverageService
    from coyote3.contracts.operations import OperationResult

FindingKind = Literal["small_variant", "cnv", "fusion", "translocation"]


class ClinicalServices:
    """Lazy clinical dependencies supplied by trusted host composition."""

    def __init__(
        self,
        *,
        dna: Callable[[], DnaService],
        structural: Callable[[], DnaStructuralService],
        rna: Callable[[], RnaService],
        classification: Callable[[], ResourceClassificationService],
        classification_document: Callable[..., dict[str, Any]],
        annotations: Callable[[], ResourceAnnotationService],
        public_annotations: Callable[[], PublicVariantAnnotations],
        catalog: Callable[[], SampleCatalogService],
        fields: Callable[[], ResourceFieldService],
        common_queries: Callable[[], CommonQueryService],
        coverage: Callable[[], CoverageService],
        biomarkers: Callable[[], BiomarkerService],
        artifacts: Callable[[], RegisteredArtifacts],
    ) -> None:
        """Bind clinical implementations without starting their infrastructure.

        Args:
            dna: Small-variant selection and review implementation.
            structural: Copy-number and translocation selection/review implementation.
            rna: Fusion selection, review and RNA context implementation.
            classification: Finding ownership, tiering and classification implementation.
            classification_document: Builds the established immutable classification content.
            annotations: Validates annotation identity, ownership and comment construction.
            public_annotations: Resolves configured public evidence through integration ports.
            catalog: Sample catalog, state changes and configuration/gene-selection workflows.
            fields: Permitted sample and reference metadata projection.
            common_queries: Shared report-context and BAM metadata lookups.
            coverage: Scoped coverage and blacklist workflows.
            biomarkers: Assay-gated HRD, MSI and TMB selection.
            artifacts: Resolves only registered report and plot artifacts.
        """
        self.dna, self.structural, self.rna = dna, structural, rna
        self.classification = classification
        self.classification_document = classification_document
        self.annotations = annotations
        self.public_annotations = public_annotations
        self.catalog, self.fields, self.common_queries = catalog, fields, common_queries
        self.coverage, self.biomarkers, self.artifacts = coverage, biomarkers, artifacts


def _sample(value: dict[str, Any] | None) -> dict[str, Any]:
    """Require the sample loaded by an authenticated sample operation."""
    if value is None:
        raise RuntimeError("Sample operation was composed without a sample identifier")
    return value


class Findings:
    """Read and review one finding family within a server-loaded sample."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        services: ClinicalServices,
        sample_id: str,
        kind: FindingKind,
    ) -> None:
        """Bind capabilities and identifiers without loading or authorizing a sample."""
        self._runtime = runtime
        self._services = services
        self._sample_id = sample_id
        self._kind = kind

    def _read_view(
        self,
        sample: dict[str, Any],
        query: AnalysisQuery,
        *,
        paginate: bool,
        include_report_context: bool,
    ) -> dict[str, Any]:
        """Invoke the canonical clinical selection and enrichment implementation for this family."""
        if self._kind == "small_variant":
            return dict(
                self._services.dna().list_variants_payload(
                    query=query, sample=sample, paginate=paginate
                )
            )
        if self._kind == "cnv":
            return dict(
                self._services.structural().list_cnvs_payload(
                    query=query, sample=sample, paginate=paginate
                )
            )
        if self._kind == "translocation":
            return dict(
                self._services.structural().list_translocations_payload(
                    query=query, sample=sample, paginate=paginate
                )
            )
        if str(sample.get("asp_category") or "").lower() != "rna":
            raise api_error(
                422,
                "RNA fusion analysis is unavailable for this sample",
                f"Sample '{sample.get('name') or self._sample_id}' has omics layer "
                f"'{sample.get('asp_category') or 'unknown'}'. RNA fusion endpoints require an RNA sample.",
                category="setup",
            )
        return dict(
            self._services.rna().list_fusions_payload(
                query=query,
                sample=sample,
                paginate=paginate,
                include_report_context=include_report_context,
            )
        )

    def view(
        self,
        query: AnalysisQuery | None = None,
        *,
        paginate: bool = True,
        include_report_context: bool = False,
    ) -> dict[str, Any]:
        """Build the clinical review context used by both SDK and HTTP consumers.

        Args:
            query: Explicit filter, search and sorting values; None applies sample defaults.
            paginate: Return the requested page when True, or the complete selection when False.
            include_report_context: Evaluate RNA report-summary rules when True.

        Returns:
            The canonical finding context, including sample, annotations and selection metadata.
        """
        return self._runtime.execute(
            f"{self._kind}.view",
            ("sample:view",),
            lambda actor, record: self._read_view(
                _sample(record),
                query or AnalysisQuery(),
                paginate=paginate,
                include_report_context=include_report_context,
            ),
            sample_id=self._sample_id,
        )

    def context(self, resource_id: str) -> dict[str, Any]:
        """Build an owned finding's clinical detail context under current read access.

        Args:
            resource_id: Finding identifier that must belong to this sample.

        Returns:
            Existing annotated detail context for this finding family.
        """

        def read(actor: Any, record: dict[str, Any] | None) -> dict[str, Any]:
            """Delegate detail preparation after authorizing the authoritative sample."""
            sample = _sample(record)
            if self._kind == "small_variant":
                return dict(
                    self._services.dna().variant_context_payload(sample=sample, var_id=resource_id)
                )
            if self._kind == "cnv":
                return dict(
                    self._services.structural().show_cnv_payload(sample=sample, cnv_id=resource_id)
                )
            if self._kind == "translocation":
                return dict(
                    self._services.structural().show_translocation_payload(
                        sample=sample, transloc_id=resource_id
                    )
                )
            return dict(
                self._services.rna().show_fusion_payload(sample=sample, fusion_id=resource_id)
            )

        return self._runtime.execute(
            f"{self._kind}.context", ("sample:view",), read, sample_id=self._sample_id
        )

    def comment_suggestion(self, query: AnalysisQuery | None = None) -> dict[str, Any]:
        """Build the established sample-summary suggestion from the complete filtered selection.

        Args:
            query: Explicit finding selection values; None applies the sample's saved filters.

        Returns:
            Sample identity, analysis modality and generated summary text without persisting it.
        """
        payload = self.view(query, paginate=False, include_report_context=True)
        sample = payload["sample"]
        return {
            "sample_id": str(sample["_id"]),
            "sample_name": str(sample.get("name") or self._sample_id),
            "analysis": "rna" if self._kind == "fusion" else "dna",
            "suggested_text": str(payload.get("ai_text") or ""),
        }

    def set_flag(self, resource_id: str, *, flag: str, value: bool) -> OperationResult:
        """Set one supported review flag after current authorization and ownership checks.

        Args:
            resource_id: Finding identifier belonging to this sample.
            flag: Supported review state, validated by FlagChange and the family service.
            value: True sets the flag; False removes it.

        Returns:
            The existing mutation summary for the sample-scoped write.
        """
        change = FlagChange.model_validate(
            {"resource_ids": [resource_id], "flag": flag, "value": value}
        )
        return self.set_flags(change)[0]

    def set_bulk_flags(
        self, resource_ids: builtins.list[str], *, flag: str, value: bool
    ) -> OperationResult:
        """Execute the existing bulk review operation after validating all selected ownership.

        Args:
            resource_ids: Selected findings; an empty selection retains the service's no-op result.
            flag: Existing bulk review flag accepted by the finding family.
            value: True sets the flag; False removes it.

        Returns:
            Aggregate mutation counts from the existing bulk operation.
        """
        if self._kind not in {"small_variant", "fusion"}:
            raise ValueError("This finding family has no bulk flag operation")

        def write(actor: Any, record: dict[str, Any] | None) -> OperationResult:
            """Validate targets before delegating the established bulk write."""
            sample = _sample(record)
            for resource_id in resource_ids:
                self._services.classification().require_resource_for_sample(
                    sample=sample, resource_type=self._kind, resource_id=resource_id
                )
            if self._kind == "small_variant":
                return self._services.dna().set_variant_bulk_flag(
                    sample=sample, resource_ids=resource_ids, apply=value, flag=flag
                )
            return self._services.rna().set_fusion_bulk_flag(
                sample=sample, fusion_ids=resource_ids, apply=value, flag=flag
            )

        return self._runtime.execute(
            f"{self._kind}.set_bulk_flags",
            ("snv:manage" if self._kind == "small_variant" else "fusion:manage",),
            write,
            sample_id=self._sample_id,
        )

    def set_comment_hidden(self, resource_id: str, comment_id: str, *, hidden: bool) -> None:
        """Change comment visibility only after authorizing the owning sample and finding.

        Args:
            resource_id: Finding whose embedded comment is being changed.
            comment_id: Comment identifier within that finding.
            hidden: True hides the comment; False restores it.
        """

        def write(actor: Any, record: dict[str, Any] | None) -> None:
            """Reuse the family mutation after the shared ownership check."""
            self._services.classification().require_resource_for_sample(
                sample=_sample(record), resource_type=self._kind, resource_id=resource_id
            )
            if self._kind == "small_variant":
                self._services.dna().set_variant_comment_hidden(
                    var_id=resource_id, comment_id=comment_id, hidden=hidden
                )
            elif self._kind == "cnv":
                self._services.structural().set_cnv_comment_hidden(
                    cnv_id=resource_id, comment_id=comment_id, hidden=hidden
                )
            elif self._kind == "translocation":
                self._services.structural().set_translocation_comment_hidden(
                    transloc_id=resource_id, comment_id=comment_id, hidden=hidden
                )
            else:
                self._services.rna().set_fusion_comment_hidden(
                    fusion_id=resource_id, comment_id=comment_id, hidden=hidden
                )

        self._runtime.execute(
            f"{self._kind}.set_comment_hidden",
            ("variant.comment:hide" if hidden else "variant.comment:unhide",),
            write,
            sample_id=self._sample_id,
        )

    def export_csv(self, query: AnalysisQuery | None = None) -> CsvExport:
        """Export the complete existing filtered selection under its established download grant.

        Args:
            query: Explicit finding filters, search and sorting; None uses saved defaults.

        Returns:
            Existing CSV formatting, sample-based filename and exported row count.
        """

        def read(actor: Any, record: dict[str, Any] | None) -> CsvExport:
            """Delegate CSV row construction and serialization to the canonical family service."""
            sample = _sample(record)
            selection = query or AnalysisQuery()
            rows: builtins.list[Any]
            if self._kind == "fusion":
                service = self._services.rna()
                payload = self._read_view(
                    sample, selection, paginate=False, include_report_context=False
                )
                rows = service.build_fusion_export_rows(payload.get("fusions", []))
                content = service.export_rows_to_csv(rows)
                suffix = "fusions"
            else:
                dna = self._services.dna()
                payload = dna.export_source_payload(query=selection, sample=sample)
                sections = payload.get("display_sections_data", {})
                if self._kind == "small_variant":
                    rows = dna.build_snv_export_rows(sections.get("snvs", []))
                    suffix = "snvs"
                elif self._kind == "cnv":
                    rows = dna.build_cnv_export_rows(
                        cnvs=sections.get("cnvs", []),
                        sample=sample,
                        assay_group=payload.get("assay_group", "unknown"),
                    )
                    suffix = "cnvs"
                else:
                    rows = dna.build_transloc_export_rows(translocs=sections.get("translocs", []))
                    suffix = "translocs"
                content = dna.export_rows_to_csv(rows)
            return CsvExport(
                filename=f"{sample.get('name', self._sample_id)}.filtered.{suffix}.csv",
                content=content,
                row_count=len(rows),
            )

        permission = {
            "small_variant": "snv:download",
            "cnv": "cnv:download",
            "translocation": "translocation:download",
            "fusion": "sample:view",
        }[self._kind]
        return self._runtime.execute(
            f"{self._kind}.export_csv", (permission,), read, sample_id=self._sample_id
        )

    def select_translocation_transcript(
        self, resource_id: str, annotation_key: str
    ) -> OperationResult:
        """Select an embedded structural annotation using the existing ownership-checked workflow.

        Args:
            resource_id: Translocation identifier owned by this sample.
            annotation_key: Existing embedded SnpEff combination key.

        Returns:
            Mutation summary from the established structural transcript selection service.
        """
        if self._kind != "translocation":
            raise ValueError("Structural transcript selection requires a translocation resource")
        return self._runtime.execute(
            "translocation.select_transcript",
            ("translocation:manage",),
            lambda actor, record: self._services.structural().select_translocation_transcript(
                sample=_sample(record), transloc_id=resource_id, key=annotation_key
            ),
            sample_id=self._sample_id,
        )

    def select_fusion_call(
        self, resource_id: str, *, call_index: str, number_of_calls: str
    ) -> None:
        """Select an existing fusion caller entry after current scope and ownership checks.

        Args:
            resource_id: Fusion identifier belonging to this sample.
            call_index: Existing caller-selection index accepted by the RNA service.
            number_of_calls: Existing serialized caller count used by that service.
        """
        if self._kind != "fusion":
            raise ValueError("Fusion caller selection requires a fusion resource")

        def write(actor: Any, record: dict[str, Any] | None) -> None:
            """Delegate ownership and caller validation to the canonical RNA service."""
            self._services.rna().select_fusion_call(
                sample=_sample(record),
                fusion_id=resource_id,
                callidx=call_index,
                num_calls=number_of_calls,
            )

        self._runtime.execute(
            "fusion.select_call", ("fusion:manage",), write, sample_id=self._sample_id
        )

    def analysis(self) -> dict[str, Any]:
        """Read the RNA expression and quality context under current sample-view authorization."""
        if self._kind != "fusion":
            raise ValueError("RNA analysis requires a fusion resource")
        return self._runtime.execute(
            "rna.analysis",
            ("sample:view",),
            lambda actor, record: self._services.rna().rna_analysis_payload(sample=_sample(record)),
            sample_id=self._sample_id,
        )

    def list(self, query: AnalysisQuery | None = None) -> FindingPage:
        """Return one filtered page after current read permission and sample-scope checks.

        Args:
            query: Explicit filtering, search, sort and page values; None uses sample defaults.

        Returns:
            Detached findings and the existing service's pagination metadata.
        """
        payload = self.view(query)
        key = {
            "small_variant": "variants",
            "cnv": "cnvs",
            "fusion": "fusions",
            "translocation": "translocations",
        }[self._kind]
        pagination = {
            name: value
            for name, value in payload.get("meta", {}).items()
            if name
            in {"total", "count", "page_count", "page", "per_page", "has_previous", "has_next"}
        }
        return FindingPage(items=deepcopy(payload[key]), pagination=pagination)

    def get(self, resource_id: str) -> dict[str, Any]:
        """Return an owned finding after permission, sample-scope and ownership checks.

        Args:
            resource_id: Finding identifier; a finding in another sample is treated as absent.

        Returns:
            Detached finding attributes without an HTTP response envelope.
        """
        return self._runtime.execute(
            f"{self._kind}.get",
            ("sample:view",),
            lambda actor, record: deepcopy(
                self._services.classification().require_resource_for_sample(
                    sample=_sample(record), resource_type=self._kind, resource_id=resource_id
                )
            ),
            sample_id=self._sample_id,
        )

    def set_flags(self, change: FlagChange) -> tuple[OperationResult, ...]:
        """Validate every finding's ownership before applying review flags.

        Args:
            change: Validated identifiers, supported flag and boolean state.

        Returns:
            Existing mutation summaries in identifier order. Each write retains
            its repository's transaction semantics; the group is not a new transaction.
        """
        change = FlagChange.model_validate(change.model_dump())

        def write(actor: Any, record: dict[str, Any] | None) -> tuple[OperationResult, ...]:
            """Check all targets before executing any of the existing guarded writes."""
            sample = _sample(record)
            classifier = self._services.classification()
            for resource_id in change.resource_ids:
                classifier.require_resource_for_sample(
                    sample=sample, resource_type=self._kind, resource_id=resource_id
                )
            results = []
            for resource_id in change.resource_ids:
                values = {"sample": sample, "apply": change.value, "flag": change.flag}
                if self._kind == "small_variant":
                    result = self._services.dna().set_variant_flag(var_id=resource_id, **values)
                elif self._kind == "cnv":
                    result = self._services.structural().set_cnv_flag(cnv_id=resource_id, **values)
                elif self._kind == "translocation":
                    result = self._services.structural().set_translocation_flag(
                        transloc_id=resource_id, **values
                    )
                else:
                    result = self._services.rna().set_fusion_flag(fusion_id=resource_id, **values)
                results.append(result)
            return tuple(results)

        permission = {
            "small_variant": "snv:manage",
            "cnv": "cnv:manage",
            "fusion": "fusion:manage",
            "translocation": "translocation:manage",
        }[self._kind]
        return self._runtime.execute(
            f"{self._kind}.set_flags", (permission,), write, sample_id=self._sample_id
        )


class SmallVariants(Findings):
    """Small-variant selection using the same clinical services as the HTTP API."""

    def tiered_variants(self, query: AnalysisQuery | None = None) -> list[dict[str, Any]]:
        """Return the complete tiered selection with existing filters and exclusions.

        Args:
            query: Explicit filter, search and intent values; None uses sample defaults.

        Returns:
            All selected tiered findings, independent of page and page-size values.
        """
        return self._runtime.execute(
            "small_variant.tiered",
            ("sample:view",),
            lambda actor, record: deepcopy(
                self._services.dna().list_variants_payload(
                    sample=_sample(record), query=query or AnalysisQuery(), paginate=False
                )["meta"]["tiered"]
            ),
            sample_id=self._sample_id,
        )

    def select_transcript(self, resource_id: str, feature_id: str) -> OperationResult:
        """Select the primary transcript after checking finding ownership.

        Args:
            resource_id: Small-variant identifier belonging to this sample.
            feature_id: Transcript feature accepted by the established selection service.

        Returns:
            The mutation summary, including any service validation error.
        """

        def write(actor: Any, record: dict[str, Any] | None) -> OperationResult:
            """Resolve the owned finding before persisting transcript selection."""
            sample = _sample(record)
            service = self._services.dna()
            service.require_variant_for_sample(sample=sample, var_id=resource_id)
            operation = service.select_variant_transcript(
                sample=sample, var_id=resource_id, feature_id=feature_id
            )
            if not operation.ok:
                raise api_error(422, operation.error or "Transcript selection failed")
            return operation

        return self._runtime.execute(
            "small_variant.select_transcript", ("snv:manage",), write, sample_id=self._sample_id
        )

    def plots(self) -> dict[str, Any]:
        """Read the DNA plot context after current sample permission and scope checks."""
        return self._runtime.execute(
            "small_variant.plots",
            ("sample:view",),
            lambda actor, record: self._services.dna().plot_context_payload(sample=_sample(record)),
            sample_id=self._sample_id,
        )

    def public_oncokb(self, resource_id: str) -> dict[str, Any]:
        """Read public OncoKB evidence for a currently authorized, sample-owned variant.

        Args:
            resource_id: Small-variant identifier that must belong to this sample.

        Returns:
            Existing public lookup or disabled result, with safe integration failures.
        """

        def read(actor: Any, record: dict[str, Any] | None) -> dict[str, Any]:
            """Establish ownership before passing the finding to the injected public lookup."""
            sample = _sample(record)
            variant = self._services.dna().require_variant_for_sample(
                sample=sample, var_id=resource_id
            )
            return dict(self._services.public_annotations().oncokb(sample, variant))

        return self._runtime.execute(
            "small_variant.public_oncokb", ("sample:view",), read, sample_id=self._sample_id
        )

    def public_clinpgx(self, resource_id: str) -> dict[str, Any]:
        """Read public selected-gene context for a currently authorized, sample-owned variant.

        Args:
            resource_id: Small-variant identifier that must belong to this sample.

        Returns:
            Existing ClinPGx result, local accession context and query metadata.
        """

        def read(actor: Any, record: dict[str, Any] | None) -> dict[str, Any]:
            """Resolve canonical finding ownership before public gene lookup."""
            variant = self._services.dna().require_variant_for_sample(
                sample=_sample(record), var_id=resource_id
            )
            return dict(self._services.public_annotations().clinpgx(variant))

        return self._runtime.execute(
            "small_variant.public_clinpgx", ("sample:view",), read, sample_id=self._sample_id
        )

    def add_to_blacklist(self, resource_id: str) -> OperationResult:
        """Create the established assay-group blacklist entry for an owned small variant.

        Args:
            resource_id: Variant identifier belonging to this authorized sample.

        Returns:
            The existing blacklist mutation summary.
        """

        def write(actor: Any, record: dict[str, Any] | None) -> OperationResult:
            """Resolve authoritative ownership and assay context before creating the entry."""
            sample = _sample(record)
            service = self._services.dna()
            variant = service.require_variant_for_sample(sample=sample, var_id=resource_id)
            config = service.configuration_resolver(sample)
            if not config:
                raise api_error(404, "Assay config not found for sample")
            return service.blacklist_variant(
                variant=variant, assay_group=config.get("asp_group", "unknown")
            )

        return self._runtime.execute(
            "small_variant.blacklist", ("snv:manage",), write, sample_id=self._sample_id
        )

    def override_blacklist(self, resource_id: str, *, override: bool) -> OperationResult:
        """Change a sample-owned blacklist override using the existing guarded write.

        Args:
            resource_id: Small-variant identifier owned by this sample.
            override: True bypasses the blacklist for this finding; False removes the override.

        Returns:
            The mutation summary for the sample-scoped override.
        """

        def write(actor: Any, record: dict[str, Any] | None) -> OperationResult:
            """Check ownership before changing the finding's override state."""
            sample = _sample(record)
            service = self._services.dna()
            service.require_variant_for_sample(sample=sample, var_id=resource_id)
            return service.set_variant_override_blacklist(
                sample=sample, var_id=resource_id, override=override
            )

        return self._runtime.execute(
            "small_variant.override_blacklist", ("snv:manage",), write, sample_id=self._sample_id
        )
