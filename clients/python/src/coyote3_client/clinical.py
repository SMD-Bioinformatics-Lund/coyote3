"""Sample analysis, finding review, comments and reporting objects for Python callers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import RootModel

from coyote3_client.endpoints import ApiEndpoint, path_segment
from coyote3_client.errors import ResourceNotLoadedError, ResponseValidationError, parse_model
from coyote3_client.metadata import SampleMetadata
from coyote3_client.models import (
    ChangeResult,
    FindingData,
    FindingDetail,
    Page,
    ReportPreview,
    ReportTrial,
    SampleContext,
    SavedReport,
)
from coyote3_client.pagination import iter_pages
from coyote3_client.resources import Resource, ResourceCollection


class FindingRows(RootModel[list[FindingData]]):
    """Validate server-selected tiered rows without changing their selection."""


class Finding:
    """Reference a finding within one sample and expose its server review operations."""

    def __init__(self, api: ApiEndpoint) -> None:
        """Bind a finding endpoint without reading or changing it.

        Args:
            api: Endpoint containing both the owning sample and finding identifier.
        """
        self.api = api
        self._detail: FindingDetail | None = None
        self._generation = api._client._session_generation

    def refresh(self) -> Finding:
        """Fetch typed finding detail; a failed refresh discards the old snapshot.

        Returns:
            This finding with current detail available through data.

        Raises:
            CoyoteAPIError: If ownership, authorization or resource lookup fails.
            ResponseValidationError: If the server detail is malformed or lacks a finding.
        """
        self._detail = None
        detail = parse_model(FindingDetail, self.api.get())
        if all(
            getattr(detail, key) is None for key in ("variant", "cnv", "fusion", "translocation")
        ):
            raise ResponseValidationError("Finding detail is missing its finding row")
        self._detail = detail
        self._generation = self.api._client._session_generation
        return self

    @property
    def data(self) -> FindingData:
        """Return the local finding row without a request.

        Raises:
            ResourceNotLoadedError: If no current-identity detail has been fetched.
        """
        if self._generation != self.api._client._session_generation:
            self._detail = None
        if self._detail is None:
            raise ResourceNotLoadedError("Call refresh() before reading finding data")
        for row in (
            self._detail.variant,
            self._detail.cnv,
            self._detail.fusion,
            self._detail.translocation,
        ):
            if row is not None:
                return row
        raise ResponseValidationError("Finding detail is missing its finding row")

    def read(self) -> FindingDetail:
        """Fetch the complete typed finding detail context using sample access checks."""
        self.refresh()
        assert self._detail is not None
        return self._detail

    def set_flag(self, flag: str, *, apply: bool = True) -> ChangeResult:
        """Apply or remove one review flag using the server's finding-specific rules.

        Args:
            flag: Exact route flag, such as interesting or false-positive.
            apply: True applies the flag; False removes it.

        Returns:
            Server change response; unsupported flags and denied permissions raise HTTP errors.

        Raises:
            ValueError: If apply is not a boolean.
        """
        if type(apply) is not bool:
            raise ValueError("apply must be a boolean")
        self._detail = None
        return parse_model(
            ChangeResult, self.api.flags[flag].request("PATCH" if apply else "DELETE")
        )


class FindingCollection:
    """Read sample findings and apply the same bulk tier operation used by the UI."""

    def __init__(self, sample_api: ApiEndpoint, segment: str, resource_type: str) -> None:
        """Bind a finding kind to its owning sample.

        Args:
            sample_api: Owning sample endpoint.
            segment: Exact collection route segment.
            resource_type: Canonical classification resource_type accepted by the server.
        """
        self._sample_api = sample_api
        self._resource_type = resource_type
        self.api = sample_api[segment]

    def list(self, **params: Any) -> Page[FindingData]:
        """Read the UI's filtered, paginated finding envelope.

        Args:
            **params: Endpoint query parameters, including page, per_page, q, sort and intent.

        Returns:
            Typed finding rows and pagination, with the original API envelope in payload.
        """
        from coyote3_client.response_pages import finding_page

        segments = {
            "small_variant": "small-variants",
            "cnv": "cnvs",
            "fusion": "fusions",
            "translocation": "translocations",
        }
        return finding_page(self.api.get(params=params), segments[self._resource_type])

    def get(self, finding_id: str) -> Finding:
        """Fetch a finding's detail using sample ownership and access checks.

        Args:
            finding_id: Finding identifier within this sample.

        Returns:
            A finding with read and set_flag methods and general endpoint access through api.
        """
        return self.ref(finding_id).refresh()

    def ref(self, finding_id: str) -> Finding:
        """Create a finding reference without a request.

        Args:
            finding_id: Finding identifier in this sample.

        Returns:
            A reference for explicit review operations or refresh().
        """
        return Finding(self.api[finding_id])

    def pages(self, *, start_page: int = 1, **params: Any) -> Iterator[Page[FindingData]]:
        """Fetch finding pages on demand with unchanged filters and ordering.

        Args:
            start_page: First page, defaulting to one.
            **params: List query parameters; use start_page instead of page.

        Yields:
            Typed pages until the server reports no continuation.
        """
        if "page" in params:
            raise ValueError("Use start_page for page iteration")
        generation = self.api._client._session_generation

        def fetch(page: int) -> Page[FindingData]:
            """Fetch a page only while the iteration's original session remains active."""
            if generation != self.api._client._session_generation:
                raise ResourceNotLoadedError("Authentication changed during page iteration")
            return self.list(**{**params, "page": page})

        yield from iter_pages(fetch, start_page=start_page)

    def iter(self, **params: Any) -> Iterator[FindingData]:
        """Yield findings across pages without prefetching subsequent pages.

        Args:
            **params: Options accepted by pages(), including intent, q, sort and page size.

        Yields:
            Server finding rows in order; concurrent edits may affect offset pagination.
        """
        for page in self.pages(**params):
            yield from page.items

    def set_tier(
        self,
        resource_ids: Sequence[str],
        tier: Literal[1, 2, 3, 4],
        *,
        apply: bool = True,
        include_automatic_text: bool = False,
        deactivation_scope: Literal["diagnosis", "group"] = "diagnosis",
    ) -> ChangeResult:
        """Assign a tier or deactivate annotations while retaining server-side history.

        Args:
            resource_ids: Identifiers belonging to this sample and finding kind.
            tier: Tier from 1 through 4.
            apply: True assigns; False deactivates the tier without deleting its annotation.
            include_automatic_text: Whether to include the server's automatic annotation text.
            deactivation_scope: Diagnosis deactivates the selected tier in the current assay
                and diagnosis. Group deactivates all finding annotations across the biological
                group's assays and diagnoses in the current namespace; requires apply=False
                and the server's tier:remove:global permission.

        Returns:
            Server change envelope. Permissions, publication and ownership checks remain server-side.

        Raises:
            ValueError: If tier, identifiers or boolean operation options are invalid.
        """
        if type(tier) is not int or tier not in (1, 2, 3, 4):
            raise ValueError("tier must be an integer from 1 through 4")
        if (
            isinstance(resource_ids, (str, bytes))
            or not resource_ids
            or any(not isinstance(identifier, str) or not identifier for identifier in resource_ids)
        ):
            raise ValueError("resource_ids must be a nonempty sequence of nonempty strings")
        if type(apply) is not bool or type(include_automatic_text) is not bool:
            raise ValueError("apply and include_automatic_text must be booleans")
        if deactivation_scope not in ("diagnosis", "group") or (
            apply and deactivation_scope == "group"
        ):
            raise ValueError("Group deactivation requires apply=False and a valid scope")
        return parse_model(
            ChangeResult,
            self._sample_api.classifications.tier.patch(
                json={
                    "resource_type": self._resource_type,
                    "resource_ids": list(resource_ids),
                    "tier": tier,
                    "apply": apply,
                    "include_automatic_text": include_automatic_text,
                    **({"deactivation_scope": "group"} if deactivation_scope == "group" else {}),
                }
            ),
        )


class VariantCollection(FindingCollection):
    """Read small variants, including the server's established tiered selection."""

    def tiered_variants(self, **params: Any) -> list[FindingData]:
        """Read all selected tiered small variants using the server's clinical rules.

        Args:
            **params: Query parameters such as intent and q. Pagination is not applied.

        Returns:
            Server-selected findings after current sample filters, classification scope
            and exclusion flags; this does not recalculate tiers in Python.
        """
        return parse_model(FindingRows, self.api.tiered.get(params=params)).root


class SampleReports:
    """Preview, save and download reports while preserving preview fingerprint checks."""

    def __init__(self, api: ApiEndpoint) -> None:
        """Bind report operations to one sample.

        Args:
            api: Sample's reports endpoint.
        """
        self.api = api

    def preview(self, report_type: Literal["dna", "rna"], **params: Any) -> ReportPreview:
        """Render a report preview without persisting a report.

        Args:
            report_type: Report modality; the server checks it against the sample.
            **params: Preview query options such as include_snapshot.

        Returns:
            Preview HTML, context and meta.preview_fingerprint for explicit saving.
        """
        return parse_model(ReportPreview, self.api[report_type].preview.get(params=params))

    def try_new(self, report_type: Literal["dna", "rna"]) -> ReportTrial:
        """Generate the alternate report for preview and optional caller-owned local files.

        Args:
            report_type: DNA or RNA modality matching this sample.

        Returns:
            HTML and base64-encoded PDF generated from the same report inputs.
            The server creates no report record or report artifact.
        """
        return parse_model(ReportTrial, self.api[report_type]["try-new"].get())

    def save(
        self,
        report_type: Literal["dna", "rna"],
        *,
        preview_fingerprint: str,
        report_format: Literal["modern", "legacy"] = "modern",
    ) -> SavedReport:
        """Persist a report only when the reviewed preview still matches current inputs.

        Args:
            report_type: dna or rna, as used in the reviewed preview.
            preview_fingerprint: Fingerprint returned by that preview; no automatic refresh or retry.
            report_format: Presentation selected in the preview; modern is the default.

        Returns:
            Saved report identifiers and artifact metadata. Changed inputs raise HTTP 409.
        """
        return parse_model(
            SavedReport,
            self.api[report_type].post(
                json={"preview_fingerprint": preview_fingerprint, "report_format": report_format}
            ),
        )

    def download(self, report_id: str, *, file_type: Literal["html", "pdf"] = "pdf") -> bytes | str:
        """Read a saved report artifact without writing a local file.

        Args:
            report_id: Persisted report identifier.
            file_type: pdf returns bytes; html returns decoded HTML text.

        Returns:
            Artifact content after report and sample access checks.

        Raises:
            ValueError: If file_type is unsupported.
            ResponseValidationError: If the content does not match the requested file type.
        """
        if file_type not in ("html", "pdf"):
            raise ValueError("file_type must be html or pdf")
        content = self.api[report_id][file_type].get()
        if file_type == "pdf" and isinstance(content, bytes):
            return content
        if file_type == "html" and isinstance(content, str):
            return content
        raise ResponseValidationError("Report content does not match the requested file type")


class SampleResource(Resource[SampleMetadata]):
    """Expose sample metadata and nested analysis and workflow objects."""

    __slots__ = ()

    @property
    def name(self) -> str | None:
        """Return the locally fetched sample name."""
        return self.data.name

    @property
    def asp_id(self) -> str | None:
        """Return the locally fetched assay identifier."""
        return self.data.asp_id

    @property
    def asp_group(self) -> str | None:
        """Return the locally fetched biological group identifier."""
        return self.data.asp_group

    @property
    def diagnosis_id(self) -> str | None:
        """Return the locally fetched diagnosis identifier."""
        return self.data.diagnosis_id

    @property
    def environment(self) -> str | None:
        """Return the locally fetched sample environment."""
        return self.data.environment

    @property
    def asp_category(self) -> str | None:
        """Return the locally fetched assay modality."""
        return self.data.asp_category

    @property
    def asp_family(self) -> str | None:
        """Return the locally fetched sequencing family."""
        return self.data.asp_family

    @property
    def ingest_status(self) -> str | None:
        """Return the locally fetched ingestion state."""
        return self.data.ingest_status

    @property
    def reported(self) -> bool | None:
        """Return the locally fetched reported flag, preserving null."""
        return self.data.reported

    @property
    def version(self) -> int | None:
        """Return the locally fetched sample version."""
        return self.data.version

    @property
    def time_added(self) -> datetime | None:
        """Return the sample's locally fetched ingestion timestamp."""
        return self.data.time_added

    @property
    def variants(self) -> VariantCollection:
        """Return the sample's SNV and small-indel collection."""
        return VariantCollection(self.api, "small-variants", "small_variant")

    @property
    def cnvs(self) -> FindingCollection:
        """Return the sample's copy-number variant collection."""
        return FindingCollection(self.api, "cnvs", "cnv")

    @property
    def fusions(self) -> FindingCollection:
        """Return the sample's RNA fusion collection."""
        return FindingCollection(self.api, "fusions", "fusion")

    @property
    def translocations(self) -> FindingCollection:
        """Return the sample's translocation collection."""
        return FindingCollection(self.api, "translocations", "translocation")

    @property
    def reports(self) -> SampleReports:
        """Return the sample's report preview, save and download operations."""
        return SampleReports(self.api.reports)

    @property
    def comments(self) -> ApiEndpoint:
        """Return comment creation and visibility endpoints; existing comments are in context()."""
        return self.api.comments

    def context(self) -> SampleContext:
        """Read the sample's UI edit context, including comments and analysis metadata."""
        return parse_model(SampleContext, self.api.edit_context.get())


class SampleCollection(ResourceCollection[SampleMetadata]):
    """Create samples with metadata attributes and nested clinical operations."""

    def get(self, resource_id: str) -> SampleResource:
        """Fetch a sample's typed metadata and expose its nested workflows.

        Args:
            resource_id: Sample identifier, checked by the server when a request is made.

        Returns:
            Sample reference with variants, cnvs, fusions, translocations, reports and comments.
        """
        return self.ref(resource_id).refresh()

    def ref(self, resource_id: str) -> SampleResource:
        """Create a sample reference without a request; refresh() loads its metadata.

        Args:
            resource_id: Sample identifier encoded as one URL segment.

        Returns:
            Reference exposing sample workflows without fetching metadata.
        """
        return SampleResource(
            self._client, f"{self._path}/{path_segment(resource_id)}", self._model
        )

    def list(self, **params: Any) -> Page[SampleMetadata]:
        """Read one page of either the live or completed sample stream.

        Args:
            **params: Catalog queries. status must be live (default) or done. page
                and per_page address the selected stream; live/done pagination
                parameters are rejected to avoid ambiguous continuation.

        Returns:
            Typed metadata and pagination for the selected stream. payload retains
            both original streams and their independent pagination metadata.
        """
        from coyote3_client.response_pages import metadata_page, sample_query

        query, status = sample_query(params)
        return metadata_page(
            self._model,
            self._client._request("GET", self._path, params=query),
            self._items_key,
            paginated=True,
            sample_stream=status,
        )
