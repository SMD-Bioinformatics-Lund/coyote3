"""Authoritative sample SDK operations shared by HTTP, workers and trusted Python callers."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal, cast

from coyote3.application.operations.clinical import (
    ClinicalServices,
    FindingKind,
    Findings,
    SmallVariants,
    _sample,
)
from coyote3.application.operations.models import (
    FileArtifact,
    SampleMutation,
    SampleRecord,
    SampleSearch,
    TierChange,
)
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.contracts.resource_fields import SampleField
    from coyote3.contracts.resource_metadata import SampleMetadata
    from coyote3.contracts.samples import ConfigurationApplyRequest


class Sample:
    """A sample reference whose operations reload current identity, grants and sample data."""

    def __init__(
        self, runtime: ApplicationRuntime, services: ClinicalServices, sample_id: str
    ) -> None:
        """Bind an identifier; constructing a reference does not read clinical data."""
        self._runtime, self._services, self.id = runtime, services, sample_id
        self.variants = SmallVariants(runtime, services, sample_id, "small_variant")
        self.cnvs = Findings(runtime, services, sample_id, "cnv")
        self.fusions = Findings(runtime, services, sample_id, "fusion")
        self.translocations = Findings(runtime, services, sample_id, "translocation")

    def read(self) -> SampleRecord:
        """Return a current sample snapshot under sample:view and current sample scope."""

        def read(actor: Any, record: dict[str, Any] | None) -> SampleRecord:
            """Project authoritative attributes into an application-owned value."""
            sample = _sample(record)
            return SampleRecord(
                id=str(sample["_id"]),
                name=str(sample.get("name") or ""),
                assay_id=str(sample.get("asp_id") or ""),
                environment=sample.get("environment"),
                attributes=deepcopy(sample),
            )

        return self._runtime.execute("sample.read", ("sample:view",), read, sample_id=self.id)

    def set_tiers(self, change: TierChange) -> None:
        """Assign or remove tiers with current curation and production-publication grants.

        Args:
            change: Explicit tier, finding family, identifiers and assignment/removal intent.

        Raises:
            AppError: Access, ownership or existing clinical configuration checks fail.
        """
        change = TierChange.model_validate(change.model_dump())

        def write(actor: Any, record: dict[str, Any] | None) -> None:
            """Validate all ownership and publication requirements before writing."""
            sample = _sample(record)
            if not change.resource_ids:
                return
            service = self._services.classification()
            for resource_id in change.resource_ids:
                service.require_resource_for_sample(
                    sample=sample, resource_type=change.resource_type, resource_id=resource_id
                )
            service.set_tier_bulk(
                sample=sample,
                resource_type=change.resource_type,
                resource_ids=change.resource_ids,
                apply=change.apply,
                class_num=change.tier,
                include_automatic_text=change.include_automatic_text,
                create_classified_variant_doc_fn=self._services.classification_document,
            )

        self._runtime.execute(
            "sample.set_tiers",
            ("snv:manage", "tier:assign" if change.apply else "tier:remove:own"),
            write,
            sample_id=self.id,
            sample_permissions=lambda sample: (
                ("annotation:publish",) if sample.get("environment") == "production" else ()
            ),
        )

    def configuration(self) -> dict[str, Any]:
        """Resolve the sample's applied configuration revision under current read access.

        Returns:
            Detached resolved configuration using the same release resolver as clinical reads.

        Raises:
            AppError: The sample is inaccessible or its configuration cannot be resolved.
        """
        return self._runtime.execute(
            "sample.configuration",
            ("sample:view",),
            lambda actor, record: deepcopy(
                self._services.dna().configuration_resolver(_sample(record))
            ),
            sample_id=self.id,
        )

    def classify(
        self, resource_type: FindingKind, resource_id: str, form_data: dict[str, Any]
    ) -> None:
        """Create a classification with authoritative ownership and configuration context.

        Args:
            resource_type: Finding family whose identity is being classified.
            resource_id: Identifier that must belong to this sample.
            form_data: Authored tier values; caller-supplied configuration scope is replaced.
        """
        from coyote3.application.interpretation.report_summary import get_tier_classification
        from coyote3.domain.dna.dna_variants import get_variant_nomenclature

        authored = deepcopy(form_data)

        def write(actor: Any, record: dict[str, Any] | None) -> None:
            """Resolve ownership and scope before the existing classification mutation."""
            sample = _sample(record)
            service = self._services.classification()
            service.require_resource_for_sample(
                sample=sample, resource_type=resource_type, resource_id=resource_id
            )
            service.classify_resource(
                resource_type=resource_type,
                form_data={**authored, **service.classification_context(sample)},
                get_tier_classification_fn=get_tier_classification,
                get_variant_nomenclature_fn=get_variant_nomenclature,
            )

        self._runtime.execute(
            "sample.classify",
            ("tier:assign",),
            write,
            sample_id=self.id,
            sample_permissions=lambda sample: (
                ("annotation:publish",) if sample.get("environment") == "production" else ()
            ),
        )

    def remove_classification(
        self, resource_type: FindingKind, resource_id: str, form_data: dict[str, Any]
    ) -> None:
        """Remove a classification through the existing sample-owned identity workflow.

        Args:
            resource_type: Canonical finding family.
            resource_id: Finding identifier belonging to this sample.
            form_data: Authored classification identity; authoritative scope is added by the service.
        """
        from coyote3.domain.dna.dna_variants import get_variant_nomenclature

        authored = deepcopy(form_data)

        def write(actor: Any, record: dict[str, Any] | None) -> None:
            """Resolve current ownership and classification context before removal."""
            sample = _sample(record)
            service = self._services.classification()
            service.require_resource_for_sample(
                sample=sample, resource_type=resource_type, resource_id=resource_id
            )
            service.remove_resource(
                resource_type=resource_type,
                form_data={**authored, **service.classification_context(sample)},
                get_variant_nomenclature_fn=get_variant_nomenclature,
            )

        self._runtime.execute(
            "sample.remove_classification",
            ("tier:remove:own",),
            write,
            sample_id=self.id,
            sample_permissions=lambda sample: (
                ("annotation:publish",) if sample.get("environment") == "production" else ()
            ),
        )

    def add_annotation(self, resource_id: str, form_data: dict[str, Any]) -> str:
        """Create a finding comment under its local or global curation and publication grants.

        Args:
            resource_id: Finding identifier whose ownership is checked by the annotation workflow.
            form_data: Authored comment and nomenclature; global marks a shared annotation.

        Returns:
            Existing finding resource label used by the HTTP change response.
        """
        from coyote3.application.interpretation.report_summary import create_comment_doc
        from coyote3.domain.dna.dna_variants import get_variant_nomenclature

        authored = deepcopy(form_data)
        shared = authored.get("global") == "global"
        permissions = ("variant.comment:add:own",) + (
            ("variant.comment:add:global",) if shared else ()
        )

        def write(actor: Any, record: dict[str, Any] | None) -> str:
            """Delegate canonical identity, context and comment construction under the bound actor."""
            return str(
                self._services.annotations().create_annotation(
                    form_data=authored,
                    target_id=resource_id,
                    get_variant_nomenclature_fn=get_variant_nomenclature,
                    create_comment_doc_fn=create_comment_doc,
                    sample=_sample(record),
                )
            )

        return self._runtime.execute(
            "sample.add_annotation",
            permissions,
            write,
            sample_id=self.id,
            sample_permissions=lambda sample: (
                ("annotation:publish",)
                if shared and sample.get("environment") == "production"
                else ()
            ),
        )

    def metadata(self) -> SampleMetadata:
        """Read permitted metadata fields after current sample permission and scope checks."""
        return cast(
            "SampleMetadata",
            self._runtime.execute(
                "sample.metadata",
                ("sample:view",),
                lambda actor, record: self._services.fields().sample_metadata(_sample(record)),
                sample_id=self.id,
            ),
        )

    def field(self, field: SampleField) -> Any:
        """Read one allowed metadata field without exposing the underlying repository.

        Args:
            field: Registered sample metadata field; unsupported names are rejected.

        Returns:
            Existing field value, including a meaningful None when the field is null or absent.
        """
        return self._runtime.execute(
            "sample.field",
            ("sample:view",),
            lambda actor, record: self._services.fields().sample_field(_sample(record), field),
            sample_id=self.id,
        )

    def genelists(self, *, target: str | None = None) -> dict[str, Any]:
        """Read selectable released gene lists for the sample's current analysis target."""
        return self._runtime.execute(
            "sample.genelists",
            ("sample:view",),
            lambda actor, record: dict(
                self._services.catalog().genelist_items_payload(
                    sample=_sample(record), target=target
                )
            ),
            sample_id=self.id,
        )

    def effective_genes(self, *, target: str | None = None) -> dict[str, Any]:
        """Read the established target-aware gene scope from the applied configuration and overrides."""
        return self._runtime.execute(
            "sample.effective_genes",
            ("sample:view",),
            lambda actor, record: dict(
                self._services.catalog().effective_genes_payload(
                    sample=_sample(record), target=target
                )
            ),
            sample_id=self.id,
        )

    def edit_context(self) -> dict[str, Any]:
        """Read the sample editing context with sample:edit:own and current sample scope."""
        return self._runtime.execute(
            "sample.edit_context",
            ("sample:edit:own",),
            lambda actor, record: dict(
                self._services.catalog().edit_context_payload(sample=_sample(record))
            ),
            sample_id=self.id,
        )

    def bam_files(self) -> dict[str, Any]:
        """Read BAM-service paths using only case/control identities from the authorized sample."""

        def read(actor: Any, record: dict[str, Any] | None) -> dict[str, Any]:
            """Resolve canonical case/control identifiers before calling the existing file query."""
            sample = _sample(record)
            case_id = sample.get("case", {}).get("id") or sample.get("case_id")
            control_id = sample.get("control", {}).get("id") or sample.get("control_id")
            ids = [text for value in (case_id, control_id) if (text := str(value or "").strip())]
            if not ids:
                raise api_error(404, "No case or control sample IDs are available for this sample")
            payload = self._services.common_queries().bam_files_payload(sample_ids=ids)
            return {
                **payload,
                "sample": {
                    "name": sample.get("name") or self.id,
                    "case_id": case_id,
                    "control_id": control_id,
                    "paired": bool(sample.get("paired")),
                },
            }

        return self._runtime.execute("sample.bam_files", ("sample:view",), read, sample_id=self.id)

    def apply_genelists(
        self, payload: dict[str, Any], *, target: str | None = None
    ) -> dict[str, Any]:
        """Apply only released, target-compatible gene lists through the existing mutation workflow."""
        return self._runtime.execute(
            "sample.apply_genelists",
            ("sample:edit:own",),
            lambda actor, record: dict(
                self._services.catalog().apply_genelists(
                    sample=_sample(record), payload=payload, sample_id=self.id, target=target
                )
            ),
            sample_id=self.id,
        )

    def save_adhoc_genes(
        self, payload: dict[str, Any], *, target: str | None = None
    ) -> dict[str, Any]:
        """Save target-aware ad hoc gene overrides using established eligibility validation."""
        return self._runtime.execute(
            "sample.save_adhoc_genes",
            ("sample:edit:own",),
            lambda actor, record: dict(
                self._services.catalog().save_adhoc_genes(
                    sample=_sample(record), payload=payload, sample_id=self.id, target=target
                )
            ),
            sample_id=self.id,
        )

    def clear_adhoc_genes(self, *, target: str | None = None) -> dict[str, Any]:
        """Remove target-specific ad hoc overrides under current sample edit access."""
        return self._runtime.execute(
            "sample.clear_adhoc_genes",
            ("sample:edit:own",),
            lambda actor, record: dict(
                self._services.catalog().clear_adhoc_genes(
                    sample=_sample(record), sample_id=self.id, target=target
                )
            ),
            sample_id=self.id,
        )

    def add_comment(self, form_data: dict[str, Any]) -> SampleMutation:
        """Create a sample comment attributed to the verified execution identity.

        Args:
            form_data: Validated authored comment fields; identity comes from the execution context.

        Returns:
            Minimal affected identity and sample modality for the established change response.
        """
        from coyote3.application.interpretation.report_summary import create_comment_doc

        def write(actor: Any, record: dict[str, Any] | None) -> SampleMutation:
            """Construct the existing comment under the bound actor, then persist it."""
            sample = _sample(record)
            self._services.catalog().add_sample_comment(
                sample_id=self.id, doc=create_comment_doc(form_data, key="sample_comment")
            )
            return SampleMutation(resource_id="new", asp_category=sample.get("asp_category"))

        return self._runtime.execute(
            "sample.add_comment", ("sample.comment:add",), write, sample_id=self.id
        )

    def set_comment_hidden(self, comment_id: str, *, hidden: bool) -> SampleMutation:
        """Change sample-comment visibility after authorizing the owning sample."""

        def write(actor: Any, record: dict[str, Any] | None) -> SampleMutation:
            """Delegate the sample-scoped embedded comment update without exposing sample contents."""
            sample = _sample(record)
            self._services.catalog().set_sample_comment_hidden(
                sample_id=self.id, comment_id=comment_id, hidden=hidden
            )
            return SampleMutation(resource_id=comment_id, asp_category=sample.get("asp_category"))

        return self._runtime.execute(
            "sample.set_comment_hidden",
            ("sample.comment:hide" if hidden else "sample.comment:unhide",),
            write,
            sample_id=self.id,
        )

    def update_filters(self, filters: dict[str, Any] | None) -> SampleMutation:
        """Merge canonical intent profiles using the established sample filter rules.

        Args:
            filters: Canonical somatic/germline profiles. None or a legacy flat profile is rejected.

        Returns:
            The canonical sample identity affected by the existing filter mutation.
        """
        from coyote3.domain.common.sample_filters import normalize_sample_filters

        incoming = deepcopy(filters or {})

        def write(actor: Any, record: dict[str, Any] | None) -> SampleMutation:
            """Keep intent normalization and validation identical for every application caller."""
            sample = _sample(record)
            intents = sample.get("analysis_intents") or ["somatic"]
            existing = normalize_sample_filters(
                sample.get("filters"),
                asp_category=str(sample.get("asp_category") or "dna"),
                analysis_intents=intents,
                canonical=True,
            )
            if not any(key in incoming for key in ("somatic", "germline")):
                raise api_error(
                    422,
                    "Filters must use the canonical intent profile structure",
                    "Submit filters.somatic.<analysis> and, where enabled, filters.germline.snv.",
                    category="validation",
                )
            merged = dict(existing)
            for intent, profile in incoming.items():
                if intent in {"somatic", "germline"} and isinstance(profile, dict):
                    merged[intent] = {**dict(existing.get(intent) or {}), **profile}
            normalized = normalize_sample_filters(
                merged,
                asp_category=str(sample.get("asp_category") or "dna"),
                analysis_intents=intents,
                canonical=True,
            )
            self._services.catalog().replace_sample_filters(sample=sample, filters=normalized)
            return SampleMutation(resource_id=str(sample["_id"]))

        return self._runtime.execute(
            "sample.update_filters", ("sample:edit:own",), write, sample_id=self.id
        )

    def reset_filters(self) -> SampleMutation:
        """Restore filters from the sample's resolved configuration with current edit access."""

        def write(actor: Any, record: dict[str, Any] | None) -> SampleMutation:
            """Resolve the applied release before invoking the established reset workflow."""
            sample = _sample(record)
            config = self._services.dna().configuration_resolver(sample)
            if not config:
                raise api_error(
                    422,
                    "ASPC could not be resolved for the sample",
                    f"Sample '{sample.get('name', self.id)}' could not resolve an assay "
                    "configuration while resetting sample filters.",
                    category="setup",
                    hint="Create the ASP and ASPC for this assay/profile before resetting filters.",
                )
            self._services.catalog().reset_sample_filters(sample=sample, assay_config=config)
            return SampleMutation(resource_id=str(sample["_id"]))

        return self._runtime.execute(
            "sample.reset_filters", ("sample:edit:own",), write, sample_id=self.id
        )

    def preview_configuration(self, *, retain_overrides: bool = False) -> dict[str, Any]:
        """Preview the latest configuration without replacing the sample's stored settings."""
        return self._runtime.execute(
            "sample.preview_configuration",
            ("sample:edit:own",),
            lambda actor, record: dict(
                self._services.catalog().preview_latest_aspc(
                    sample=_sample(record), retain_overrides=retain_overrides
                )
            ),
            sample_id=self.id,
        )

    def apply_configuration(self, request: ConfigurationApplyRequest) -> SampleMutation:
        """Apply an explicitly reviewed configuration using the existing version/hash guards."""

        def write(actor: Any, record: dict[str, Any] | None) -> SampleMutation:
            """Keep sample concurrency and release verification inside the canonical service."""
            sample = _sample(record)
            applied = self._services.catalog().apply_latest_aspc(
                sample=sample, **request.model_dump()
            )
            return SampleMutation(resource_id=str(sample["_id"]), details={"applied_aspc": applied})

        return self._runtime.execute(
            "sample.apply_configuration", ("sample:edit:own",), write, sample_id=self.id
        )

    def report_context(self, report_id: str) -> dict[str, Any]:
        """Read a saved report and finding snapshot context belonging to the authorized sample."""
        return self._runtime.execute(
            "sample.report_context",
            ("report:view",),
            lambda actor, record: dict(
                self._services.catalog().report_context_payload(
                    sample=_sample(record), report_id=report_id, sample_id=self.id
                )
            ),
            sample_id=self.id,
        )

    def report_artifact(
        self, report_id: str, *, file_type: Literal["html", "pdf"] = "html", inline: bool = False
    ) -> FileArtifact:
        """Resolve only the registered artifact of a report owned by the authorized sample."""
        context = self.report_context(report_id)
        pdf = file_type == "pdf"
        return self._services.artifacts().report(
            context.get("pdf_filepath" if pdf else "filepath"),
            context.get("pdf_report_name" if pdf else "report_name"),
            media_type="application/pdf" if pdf else "text/html",
            inline=inline and not pdf,
        )

    def plot(self, filename: str) -> FileArtifact:
        """Resolve the registered CNV raster profile after current sample authorization."""
        from coyote3.config.constants import primary_analysis_file_key

        def read(actor: Any, record: dict[str, Any] | None) -> FileArtifact:
            """Select the registered analysis artifact before invoking filesystem validation."""
            sample = _sample(record)
            stored_files = sample.get("files")
            files = stored_files if isinstance(stored_files, dict) else {}
            profile = files.get(primary_analysis_file_key("dna", "CNV_PROFILE"))
            if not isinstance(profile, dict) or not profile.get("path"):
                raise api_error(404, "No CNV profile is registered for this sample")
            return self._services.artifacts().plot(str(profile["path"]), filename)

        return self._runtime.execute("sample.plot", ("sample:view",), read, sample_id=self.id)

    def coverage(self, *, cutoff: int = 500) -> dict[str, Any]:
        """Read the existing coverage analysis at a positive minimum-depth cutoff."""
        if cutoff < 1:
            raise ValueError("Coverage cutoff must be positive")
        return self._runtime.execute(
            "sample.coverage",
            ("sample:view",),
            lambda actor, record: dict(
                self._services.coverage().sample_payload(sample=_sample(record), cov_cutoff=cutoff)
            ),
            sample_id=self.id,
        )

    def biomarkers(self, analysis: Literal["HRD", "MSI", "TMB"]) -> dict[str, Any]:
        """Read only measurements enabled by the sample's applied clinical configuration."""
        return self._runtime.execute(
            "sample.biomarkers",
            ("sample:view",),
            lambda actor, record: dict(
                self._services.biomarkers().list_payload(
                    sample=_sample(record), analysis_type=analysis
                )
            ),
            sample_id=self.id,
        )


class Samples:
    """Create sample references and retrieve authorized sample snapshots."""

    def __init__(self, runtime: ApplicationRuntime, services: ClinicalServices) -> None:
        """Bind trusted runtime and clinical capabilities."""
        self._runtime, self._services = runtime, services

    def ref(self, sample_id: str) -> Sample:
        """Return a reference by sample name or identifier without retrieving data."""
        if not sample_id.strip():
            raise ValueError("Sample identifier must not be blank")
        return Sample(self._runtime, self._services, sample_id)

    def get(self, sample_id: str) -> SampleRecord:
        """Load a sample snapshot after current permission and scope checks."""
        return self.ref(sample_id).read()

    def list(self, query: SampleSearch | None = None) -> dict[str, Any]:
        """List the existing scoped live/reported sample catalog with explicit query values.

        Args:
            query: Search, environment and pagination values; None uses application defaults.

        Returns:
            The existing two-section sample catalog within current actor assignments.
        """
        from coyote3.config.constants import DEFAULT_ENVIRONMENT

        query = query or SampleSearch()
        if query.added_from and query.added_until and query.added_until <= query.added_from:
            raise api_error(
                400,
                "Invalid sample date range",
                "added_until must be later than added_from.",
                category="validation",
            )
        values = query.model_dump(exclude={"live_per_page", "done_per_page", "profile_scope"})
        return self._runtime.execute(
            "samples.list",
            ("sample:view",),
            lambda actor, sample: dict(
                self._services.catalog().samples_payload(
                    user=actor,
                    **values,
                    per_live_page=query.live_per_page or query.per_page,
                    per_done_page=query.done_per_page or query.per_page,
                    profile_scope=query.profile_scope or DEFAULT_ENVIRONMENT,
                )
            ),
        )

    def navigation_counts(self, *, profile_scope: str | None = None) -> dict[str, Any]:
        """Read live assay-navigation counts using the actor's current assignments."""
        from coyote3.config.constants import DEFAULT_ENVIRONMENT

        return self._runtime.execute(
            "samples.navigation_counts",
            ("sample:view",),
            lambda actor, sample: dict(
                self._services.catalog().navigation_counts_payload(
                    user=actor, profile_scope=profile_scope or DEFAULT_ENVIRONMENT
                )
            ),
        )
