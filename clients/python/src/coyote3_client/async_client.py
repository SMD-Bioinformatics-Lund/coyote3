"""Native async HTTP access with the same wire models and server-owned authorization."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Generic, Literal, Self, TypeVar

import httpx

from coyote3_client.clinical import FindingRows
from coyote3_client.endpoints import path_segment
from coyote3_client.errors import (
    ResourceNotLoadedError,
    ResponseValidationError,
    parse_model,
    raise_for_api_status,
)
from coyote3_client.metadata import (
    AssayMetadata,
    ConfigurationMetadata,
    DiagnosisMetadata,
    GeneListMetadata,
    GroupMetadata,
    ResourceMetadata,
    SampleMetadata,
)
from coyote3_client.models import (
    FindingData,
    FindingDetail,
    Page,
    ReportPreview,
    ReportTrial,
    SavedReport,
    SessionResponse,
    SessionUser,
)
from coyote3_client.resources import CoyoteClient

ModelT = TypeVar("ModelT", bound=ResourceMetadata)


class AsyncApiEndpoint:
    """Await explicit HTTP methods on fluent paths; path construction performs no I/O."""

    def __init__(self, client: AsyncCoyoteClient, path: str = "") -> None:
        """Bind a client and an already encoded API-relative path."""
        self._client, self._path = client, path

    def __getitem__(self, segment: str) -> AsyncApiEndpoint:
        """Append one safely encoded identifier or route segment."""
        return AsyncApiEndpoint(
            self._client, "/".join(filter(None, (self._path, path_segment(segment))))
        )

    def __getattr__(self, name: str) -> AsyncApiEndpoint:
        """Append a route attribute using the synchronous client's spelling rules."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name.replace("_", "-")]

    async def request(self, method: str, **kwargs: Any) -> Any:
        """Send one HTTP request with explicit HTTPX parameters and no automatic retries.

        Args:
            method: HTTP method, such as GET or POST.
            **kwargs: HTTPX params, json, data, files or content. The client owns
                authentication headers; callers cannot replace them.

        Returns:
            Decoded JSON, text, bytes, or None for an empty response.

        Raises:
            CoyoteAPIError: The server rejects the request.
            httpx.HTTPError: A connection, TLS or timeout failure occurs.
        """
        return await self._client._request(method, self._path, **kwargs)

    async def get(self, **kwargs: Any) -> Any:
        """Read this endpoint with explicit query parameters."""
        return await self.request("GET", **kwargs)

    async def post(self, **kwargs: Any) -> Any:
        """Submit an explicit mutation, upload or workflow request."""
        return await self.request("POST", **kwargs)

    async def put(self, **kwargs: Any) -> Any:
        """Replace this endpoint's value."""
        return await self.request("PUT", **kwargs)

    async def patch(self, **kwargs: Any) -> Any:
        """Apply an explicit partial update."""
        return await self.request("PATCH", **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete or clear this endpoint."""
        return await self.request("DELETE", **kwargs)

    @asynccontextmanager
    async def stream(self, method: str = "GET", **kwargs: Any) -> AsyncIterator[httpx.Response]:
        """Yield an authenticated stream and close it on exit or cancellation."""
        async with self._client._stream(method, self._path, **kwargs) as response:
            yield response


class AsyncResource(Generic[ModelT]):
    """Typed local metadata with explicit awaitable refresh and endpoint access."""

    def __init__(self, client: AsyncCoyoteClient, path: str, model: type[ModelT]) -> None:
        """Bind a resource without fetching it; model declares its permitted attributes."""
        self._client, self._path, self._model = client, path, model
        self._generation = client._session_generation
        self._data: ModelT | None = None

    @property
    def data(self) -> ModelT:
        """Read a snapshot only while its authenticated session remains current."""
        if self._generation != self._client._session_generation:
            self._data = None
        if self._data is None:
            raise ResourceNotLoadedError("Call await refresh() before reading resource metadata")
        return self._data

    def __getattr__(self, name: str) -> Any:
        """Read declared metadata without hidden network requests."""
        if name not in self._model.model_fields:
            raise AttributeError(name)
        return getattr(self.data, name)

    def __dir__(self) -> list[str]:
        """Include permitted metadata names in interactive completion."""
        return sorted(set(super().__dir__()) | set(self._model.model_fields))

    @property
    def api(self) -> AsyncApiEndpoint:
        """Return the resource's general HTTP endpoint."""
        return AsyncApiEndpoint(self._client, self._path)

    async def refresh(self) -> Self:
        """Fetch and validate metadata, discarding stale snapshots before a failed fetch.

        Returns:
            This resource with a typed snapshot for the current session.

        Raises:
            CoyoteAPIError: Current server permissions or sample ownership reject the read.
            ResponseValidationError: The response violates the metadata contract.
        """
        self._data = None
        self._data = parse_model(self._model, await self.api.metadata.get())
        self._generation = self._client._session_generation
        return self


class AsyncCollection(Generic[ModelT]):
    """Read metadata and server-controlled pages without importing application models."""

    def __init__(
        self,
        client: AsyncCoyoteClient,
        path: str,
        model: type[ModelT],
        items_key: str,
        *,
        paginated: bool = True,
    ) -> None:
        """Bind the existing list-envelope key and metadata schema for this collection."""
        self._client, self._path, self._model, self._items_key = client, path, model, items_key
        self._paginated = paginated

    def ref(self, resource_id: str) -> AsyncResource[ModelT]:
        """Create an unfetched reference using a safely encoded resource identifier."""
        return AsyncResource(self._client, f"{self._path}/{path_segment(resource_id)}", self._model)

    async def get(self, resource_id: str) -> AsyncResource[ModelT]:
        """Fetch one typed metadata snapshot and return its reference."""
        return await self.ref(resource_id).refresh()

    async def list(self, **params: Any) -> Page[ModelT]:
        """Fetch one existing collection envelope, preserving server pagination semantics.

        Args:
            **params: List query options. Samples use status=live/done and page/per_page;
                other collections accept their existing API filters.

        Returns:
            A typed page with the original response retained in payload.

        Raises:
            ValueError: Sample pagination options address ambiguous streams.
            ResponseValidationError: Rows or pagination violate the wire contract.
        """
        from coyote3_client.response_pages import metadata_page, sample_query

        query, stream = sample_query(params) if self._path == "samples" else (params, None)
        payload = await AsyncApiEndpoint(self._client, self._path).get(params=query)
        return metadata_page(
            self._model, payload, self._items_key, paginated=self._paginated, sample_stream=stream
        )

    async def pages(self, *, start_page: int = 1, **params: Any) -> AsyncIterator[Page[ModelT]]:
        """Yield validated pages lazily, stopping when the server reports no continuation.

        Args:
            start_page: Positive first page, defaulting to one.
            **params: Endpoint filters and page size; use start_page instead of page.

        Yields:
            Pages in server order; ending iteration avoids subsequent requests.

        Raises:
            ValueError: The starting page is invalid or options are ambiguous.
            ResourceNotLoadedError: Identity changes during iteration.
            ResponseValidationError: Pagination repeats or an empty page claims continuation.
        """
        if type(start_page) is not int or start_page < 1 or "page" in params:
            raise ValueError("Use a positive start_page rather than page")
        if not self._paginated and start_page != 1:
            raise ValueError("This collection has only one page")
        generation, number = self._client._session_generation, start_page
        while True:
            if generation != self._client._session_generation:
                raise ResourceNotLoadedError("Authentication changed during page iteration")
            page = await self.list(**({**params, "page": number} if self._paginated else params))
            if page.pagination.page != number or (page.pagination.has_next and not page.items):
                raise ResponseValidationError("Server pagination did not advance correctly")
            yield page
            if not page.pagination.has_next:
                return
            number += 1

    async def iter(self, **params: Any) -> AsyncIterator[ModelT]:
        """Yield individual metadata rows using lazy server pagination."""
        async for page in self.pages(**params):
            for item in page.items:
                yield item


class AsyncFindings:
    """Typed sample-finding reads; the server owns filtering and classification."""

    def __init__(self, sample: AsyncApiEndpoint, segment: str) -> None:
        """Bind an actual analysis route beneath its owning sample."""
        self.api, self._segment = sample[segment], segment

    async def list(self, **params: Any) -> Page[FindingData]:
        """Fetch a filtered finding page using the established UI response envelope."""
        from coyote3_client.response_pages import finding_page

        return finding_page(await self.api.get(params=params), self._segment)

    async def get(self, finding_id: str) -> FindingDetail:
        """Read finding detail after server-side sample ownership checks."""
        return parse_model(FindingDetail, await self.api[finding_id].get())


class AsyncVariants(AsyncFindings):
    """Read the server-selected tiered small variants without recalculating clinical rules."""

    async def tiered_variants(self, **params: Any) -> list[FindingData]:
        """Return the complete server-selected tiered list for these query options.

        Args:
            **params: Supported options such as intent and q; no pagination is applied.

        Returns:
            Typed findings after server filtering, scope and classification rules.
        """
        return parse_model(FindingRows, await self.api.tiered.get(params=params)).root


class AsyncReports:
    """Await report previews, temporary trials and explicit fingerprint-protected saves."""

    def __init__(self, api: AsyncApiEndpoint) -> None:
        """Bind the sample's existing reports endpoint."""
        self.api = api

    async def preview(self, report_type: Literal["dna", "rna"], **params: Any) -> ReportPreview:
        """Read an existing preview and its fingerprint without saving a report."""
        return parse_model(ReportPreview, await self.api[report_type].preview.get(params=params))

    async def try_new(self, report_type: Literal["dna", "rna"]) -> ReportTrial:
        """Generate a matching temporary HTML/PDF pair without server report persistence.

        Args:
            report_type: DNA or RNA modality matching the sample.

        Returns:
            HTML and base64 PDF content; the caller decides whether to write local files.
        """
        return parse_model(ReportTrial, await self.api[report_type]["try-new"].get())

    async def save(
        self, report_type: Literal["dna", "rna"], *, preview_fingerprint: str
    ) -> SavedReport:
        """Save only the explicitly reviewed fingerprint; never refresh or retry a mutation."""
        return parse_model(
            SavedReport,
            await self.api[report_type].post(json={"preview_fingerprint": preview_fingerprint}),
        )


class AsyncSample(AsyncResource[SampleMetadata]):
    """Sample metadata and awaitable clinical workflows using the existing HTTP routes."""

    @property
    def variants(self) -> AsyncVariants:
        """Return small-variant operations without fetching data."""
        return AsyncVariants(self.api, "small-variants")

    @property
    def cnvs(self) -> AsyncFindings:
        """Return copy-number operations without fetching data."""
        return AsyncFindings(self.api, "cnvs")

    @property
    def fusions(self) -> AsyncFindings:
        """Return RNA fusion operations without fetching data."""
        return AsyncFindings(self.api, "fusions")

    @property
    def translocations(self) -> AsyncFindings:
        """Return DNA translocation operations without fetching data."""
        return AsyncFindings(self.api, "translocations")

    @property
    def reports(self) -> AsyncReports:
        """Return report operations without rendering a report."""
        return AsyncReports(self.api.reports)


class AsyncSamples(AsyncCollection[SampleMetadata]):
    """Create typed async samples and preserve independently paginated sample streams."""

    def ref(self, resource_id: str) -> AsyncSample:
        """Create an unfetched sample reference."""
        return AsyncSample(self._client, f"samples/{path_segment(resource_id)}", SampleMetadata)

    async def get(self, resource_id: str) -> AsyncSample:
        """Fetch sample metadata and expose its nested clinical operations."""
        return await self.ref(resource_id).refresh()


class AsyncCoyoteClient:
    """Own a native HTTPX async transport and a revocable bearer session."""

    def __init__(
        self,
        base_url: str,
        *,
        cookie_name: str = "coyote3_api_session",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Configure an HTTP(S) origin, optional mount prefix, TLS verification and timeout.

        Args:
            base_url: Public origin with an optional deployment prefix, without /api/v1.
            cookie_name: Configured server cookie name used to capture the issued bearer token.
            timeout: Timeout in seconds for each HTTPX operation, defaulting to 30.
            transport: Optional async transport for tests; None uses verified network access.

        Raises:
            ValueError: The URL is invalid or contains credentials, query or fragment.
        """
        from coyote3_client.transport import validate_base_url

        validate_base_url(base_url)
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self._cookie_name = cookie_name
        self._token: str | None = None
        self._session_generation = 0
        self.user: SessionUser | None = None
        self.api = AsyncApiEndpoint(self)
        self.samples = AsyncSamples(self, "samples", SampleMetadata, "live_samples")
        self.asp = AsyncCollection(self, "resources/asp", AssayMetadata, "panels")
        self.aspc = AsyncCollection(self, "resources/aspc", ConfigurationMetadata, "assay_configs")
        self.assay_groups = AsyncCollection(
            self, "resources/assay-groups", GroupMetadata, "groups", paginated=False
        )
        self.diagnoses = AsyncCollection(
            self, "resources/diagnoses", DiagnosisMetadata, "diagnoses", paginated=False
        )
        self.genelists = AsyncCollection(self, "resources/genelists", GeneListMetadata, "genelists")

    def _clear_session(self) -> None:
        """Discard credentials and invalidate all previously loaded metadata snapshots."""
        self._token, self.user = None, None
        self._session_generation += 1
        self._http.cookies.clear()

    @property
    def session_token(self) -> str | None:
        """Return the validated bearer credential, or None before login or after logout.

        Treat this value as a secret. It grants the current session's server-enforced
        permissions and must not be included in logs or ordinary diagnostic output.
        """
        return self._token

    async def login(self, *, username: str, password: str, provider: str) -> SessionUser:
        """Authenticate through the existing provider endpoint without retaining the password.

        Args:
            username: Local username or LDAP identity accepted by the deployment.
            password: Secret used only for this login request.
            provider: Explicit configured provider, such as local or ldap.

        Returns:
            Typed user metadata, also stored in client.user.

        Raises:
            AuthenticationError: Credentials or the selected provider are rejected.
            ValueError: The configured session cookie is absent.
            httpx.HTTPError: Transport or timeout failure prevents authentication.
        """
        self._clear_session()
        response = await self._http.post(
            "api/v1/auth/sessions",
            json={"username": username, "password": password, "provider": provider},
        )
        self._http.cookies.clear()
        raise_for_api_status(response)
        token = response.cookies.get(self._cookie_name)
        if not token:
            raise ValueError(
                "Login did not return the configured session cookie; check cookie_name"
            )
        self.user = parse_model(SessionResponse, CoyoteClient._decode(response)).user
        self._token = token
        return self.user

    async def login_with_token(self, token: str) -> SessionUser:
        """Validate an existing opaque server token before enabling resource requests.

        Args:
            token: Nonempty session token, without the Bearer prefix.

        Returns:
            Typed metadata for the verified user.

        Raises:
            ValueError: Token is empty.
            AuthenticationError: The server rejects an invalid, expired or revoked token.
        """
        self._clear_session()
        if not token:
            raise ValueError("A session token is required")
        response = await self._http.get(
            "api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        self._http.cookies.clear()
        raise_for_api_status(response)
        self.user = parse_model(SessionResponse, CoyoteClient._decode(response)).user
        self._token = token
        return self.user

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send an authenticated request and preserve typed server errors and response values."""
        if not self._token:
            raise RuntimeError("Log in before accessing resources")
        response = await self._http.request(
            method, f"api/v1/{path}", headers={"Authorization": f"Bearer {self._token}"}, **kwargs
        )
        raise_for_api_status(response)
        return CoyoteClient._decode(response)

    @asynccontextmanager
    async def _stream(self, method: str, path: str, **kwargs: Any) -> AsyncIterator[httpx.Response]:
        """Yield an authenticated response stream and close it during cancellation or exit."""
        if not self._token:
            raise RuntimeError("Log in before accessing resources")
        async with self._http.stream(
            method, f"api/v1/{path}", headers={"Authorization": f"Bearer {self._token}"}, **kwargs
        ) as response:
            if response.is_error:
                await response.aread()
            raise_for_api_status(response)
            yield response

    async def logout(self) -> None:
        """Revoke the server session and clear local credentials even when revocation fails."""
        try:
            if self._token:
                await self._request("DELETE", "auth/sessions/current")
        finally:
            self._clear_session()

    async def aclose(self) -> None:
        """Close async connections and discard credentials without revoking the server token."""
        self._clear_session()
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        """Return this client for an async context manager."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close connections while preserving the active exception or cancellation."""
        await self.aclose()
