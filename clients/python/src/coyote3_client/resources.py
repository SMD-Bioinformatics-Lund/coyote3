"""Synchronous, authenticated resource access for Python scripts and notebooks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Generic, Self, TypeVar

import httpx

from coyote3_client.endpoints import ApiEndpoint, path_segment
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
from coyote3_client.models import Page, SessionResponse, SessionUser
from coyote3_client.pagination import iter_pages

MetadataT = TypeVar("MetadataT", bound=ResourceMetadata)


class Resource(Generic[MetadataT]):
    """A local metadata snapshot with explicit refresh and resource endpoint access."""

    __slots__ = ("_client", "_path", "_model", "_data", "_generation")

    def __init__(self, client: CoyoteClient, path: str, model: type[MetadataT]) -> None:
        """Bind a resource reference without making a request.

        Args:
            client: Client whose current session authorizes each read.
            path: Encoded API-relative resource path.
            model: Typed permitted metadata response contract.
        """
        self._client = client
        self._path = path
        self._model = model
        self._data: MetadataT | None = None
        self._generation = client._session_generation

    def __getattr__(self, name: str) -> Any:
        """Read one permitted attribute from the local snapshot without making a request.

        Args:
            name: Metadata key, such as asp_id or reported.

        Returns:
            Cached metadata value, including None for optional null values.

        Raises:
            AttributeError: If the key is outside the resource contract.
            ResourceNotLoadedError: If refresh() is needed or authentication changed.
        """
        if name not in self._model.model_fields:
            raise AttributeError(f"Unsupported resource attribute: {name}")
        return getattr(self.data, name)

    def __dir__(self) -> list[str]:
        """Include permitted attributes in interactive completion."""
        return sorted(set(super().__dir__()) | set(self._model.model_fields))

    @property
    def data(self) -> MetadataT:
        """Return typed local metadata; authentication changes require explicit refresh.

        Raises:
            ResourceNotLoadedError: If no snapshot is loaded for the client's current identity.
        """
        if self._generation != self._client._session_generation:
            self._data = None
        if self._data is None:
            raise ResourceNotLoadedError("Call refresh() before reading resource metadata")
        return self._data

    def refresh(self) -> Self:
        """Fetch one metadata snapshot and return this resource.

        A failed fetch discards the old snapshot. No attribute read sends HTTP requests.

        Returns:
            This resource with validated data and the current authentication generation.

        Raises:
            CoyoteAPIError: If the server rejects the read.
            ResponseValidationError: If the response violates the metadata contract.
        """
        self._data = None
        snapshot = self._client._request("GET", f"{self._path}/metadata")
        self._data = parse_model(self._model, snapshot)
        self._generation = self._client._session_generation
        return self

    @property
    def api(self) -> ApiEndpoint:
        """Return general endpoint access beneath this resource, without making a request."""
        return ApiEndpoint(self._client, self._path)


class ResourceCollection(Generic[MetadataT]):
    """Fetch typed resource metadata and iterate server-managed collection pages."""

    def __init__(
        self,
        client: CoyoteClient,
        path: str,
        model: type[MetadataT],
        *,
        items_key: str,
        paginated: bool = True,
    ) -> None:
        """Bind a collection to its API path and allowed fields.

        Args:
            client: Authenticated transport owner.
            path: API-relative collection path.
            model: Metadata response model.
            items_key: Existing API list-envelope key containing rows.
            paginated: Whether the endpoint returns a pagination object.
        """
        self._client = client
        self._path = path
        self._model = model
        self._items_key = items_key
        self._paginated = paginated

    def get(self, resource_id: str) -> Resource[MetadataT]:
        """Fetch resource metadata in one request, checking existence and permissions.

        Args:
            resource_id: Nonempty business identifier, encoded as one URL segment.

        Returns:
            A resource containing a validated, locally readable metadata snapshot.

        Raises:
            ValueError: If the identifier is empty, a dot segment or contains path separators.
        """
        return self.ref(resource_id).refresh()

    def ref(self, resource_id: str) -> Resource[MetadataT]:
        """Create a reference without a request; refresh() loads its metadata.

        Args:
            resource_id: Resource business identifier encoded as one path segment.

        Returns:
            A reference suitable for endpoint operations without a metadata fetch.
        """
        return Resource(self._client, f"{self._path}/{path_segment(resource_id)}", self._model)

    def _page(self, payload: object, rows: object, pagination: object) -> Page[MetadataT]:
        """Validate a list envelope and project rows onto the typed metadata contract.

        Args:
            payload: Complete API response retained for explicit access to extra fields.
            rows: Resource row array selected from the established envelope.
            pagination: Server pagination metadata.

        Returns:
            Typed page preserving the original response.

        Raises:
            ResponseValidationError: For missing rows or malformed metadata.
        """
        from coyote3_client.response_pages import metadata_rows_page

        return metadata_rows_page(self._model, payload, rows, pagination)

    def list(self, **params: Any) -> Page[MetadataT]:
        """Read one typed collection page with the original API envelope in payload.

        Args:
            **params: Query parameters supported by the corresponding list endpoint.

        Returns:
            Metadata rows and validated pagination; computed values absent in list rows remain null.

        Raises:
            httpx.HTTPStatusError: If authentication, permissions or validation fail.
        """
        payload = self._client._request("GET", self._path, params=params)
        if not isinstance(payload, dict):
            raise ResponseValidationError("Resource list response must be an object")
        rows = payload.get(self._items_key)
        pagination = payload.get("pagination")
        if not self._paginated and isinstance(rows, list):
            pagination = {
                "page": 1,
                "per_page": max(1, len(rows)),
                "total": len(rows),
                "has_next": False,
            }
        return self._page(payload, rows, pagination)

    def pages(self, *, start_page: int = 1, **params: Any) -> Iterator[Page[MetadataT]]:
        """Fetch collection pages on demand, preserving filters and server ordering.

        Args:
            start_page: First page to read; must be a positive integer.
            **params: Query filters and page size; use start_page rather than page.

        Yields:
            Typed pages until has_next is false; no subsequent request is made after early stopping.
        """
        if "page" in params:
            raise ValueError("Use start_page for page iteration")
        if not self._paginated and start_page != 1:
            raise ValueError("This collection has only one page")
        generation = self._client._session_generation

        def fetch(page: int) -> Page[MetadataT]:
            """Fetch the next page only while the original session remains active."""
            if generation != self._client._session_generation:
                raise ResourceNotLoadedError("Authentication changed during page iteration")
            return self.list(**({**params, "page": page} if self._paginated else params))

        yield from iter_pages(
            fetch,
            start_page=start_page,
        )

    def iter(self, **params: Any) -> Iterator[MetadataT]:
        """Yield typed metadata rows across pages.

        Args:
            **params: The same options as pages(), including start_page and query filters.

        Yields:
            Metadata snapshots in server order. Concurrent server changes can affect pagination.
        """
        for page in self.pages(**params):
            yield from page.items


class CoyoteClient:
    """Access Coyote3 resources and UI workflows using an authenticated bearer session."""

    def __init__(
        self,
        base_url: str,
        *,
        cookie_name: str = "coyote3_api_session",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a persistent HTTP client and its resource collections.

        Args:
            base_url: Public HTTP(S) origin with any deployment mount prefix, without /api/v1.
            cookie_name: Installation's API_SESSION_COOKIE_NAME; used to capture login tokens.
            timeout: HTTP timeout in seconds, defaulting to 30.
            transport: Optional HTTPX transport for testing; None uses verified network HTTPS.

        Raises:
            ValueError: If the URL lacks an HTTP(S) origin or contains credentials/query/fragment.
        """
        from coyote3_client.transport import validate_base_url

        validate_base_url(base_url)
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self._cookie_name = cookie_name
        self._token: str | None = None
        self._session_generation = 0
        self.user: SessionUser | None = None
        from coyote3_client.clinical import SampleCollection

        self.api = ApiEndpoint(self)
        self.samples = SampleCollection(self, "samples", SampleMetadata, items_key="live_samples")
        self.asp = ResourceCollection(self, "resources/asp", AssayMetadata, items_key="panels")
        self.aspc = ResourceCollection(
            self, "resources/aspc", ConfigurationMetadata, items_key="assay_configs"
        )
        self.assay_groups = ResourceCollection(
            self, "resources/assay-groups", GroupMetadata, items_key="groups", paginated=False
        )
        self.diagnoses = ResourceCollection(
            self, "resources/diagnoses", DiagnosisMetadata, items_key="diagnoses", paginated=False
        )
        self.genelists = ResourceCollection(
            self, "resources/genelists", GeneListMetadata, items_key="genelists"
        )

    @property
    def session_token(self) -> str | None:
        """Return the validated bearer credential, or None before login or after logout.

        Treat this value as a secret. It grants the current session's server-enforced
        permissions and must not be included in logs or ordinary diagnostic output.
        """
        return self._token

    def login(self, *, username: str, password: str, provider: str) -> SessionUser:
        """Authenticate with an explicit provider and retain the issued bearer session.

        Args:
            username: Local username or LDAP email identity.
            password: Password for the selected provider; never stored on the client.
            provider: Explicit center-enabled provider, such as local or ldap.

        Returns:
            Authenticated user metadata, also available as client.user.

        Raises:
            httpx.HTTPStatusError: If authentication fails.
            ValueError: If the configured session cookie is missing from the response.
        """
        self._clear_session()
        response = self._http.post(
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
        user = parse_model(SessionResponse, self._decode(response)).user
        self._token = token
        self.user = user
        return user

    def login_with_token(self, token: str) -> SessionUser:
        """Validate and retain an existing opaque API session token.

        Args:
            token: Existing session token, without a Bearer prefix.

        Returns:
            Authenticated user metadata.

        Raises:
            ValueError: If the token is empty.
            httpx.HTTPStatusError: If the token is expired or invalid.
        """
        self._clear_session()
        if not token:
            raise ValueError("A session token is required")
        response = self._http.get(
            "api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        self._http.cookies.clear()
        raise_for_api_status(response)
        user = parse_model(SessionResponse, self._decode(response)).user
        self._token = token
        self.user = user
        return user

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send an authenticated request and preserve server errors and JSON values.

        Args:
            method: HTTP method for the operation.
            path: API-relative path controlled by the resource wrappers.
            **kwargs: HTTPX request parameters such as query parameters.

        Returns:
            Decoded JSON, text, binary content or None for an empty response.

        Raises:
            RuntimeError: If no authenticated session is available.
            httpx.HTTPStatusError: For any unsuccessful API response.
        """
        if not self._token:
            raise RuntimeError("Log in before accessing resources")
        response = self._http.request(
            method,
            f"api/v1/{path}",
            headers={"Authorization": f"Bearer {self._token}"},
            **kwargs,
        )
        raise_for_api_status(response)
        return self._decode(response)

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        """Decode successful content without silently accepting malformed JSON.

        Args:
            response: Successful HTTP response.

        Returns:
            JSON values, text, bytes or None for empty content.

        Raises:
            ResponseValidationError: If JSON media contains invalid JSON.
        """
        if not response.content:
            return None
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type == "application/json" or media_type.endswith("+json"):
            try:
                return response.json()
            except ValueError:
                raise ResponseValidationError("API returned malformed JSON") from None
        if media_type.startswith("text/"):
            return response.text
        return response.content

    def _clear_session(self) -> None:
        """Forget local authentication state without revoking a server session."""
        self._token = None
        self.user = None
        self._session_generation += 1
        self._http.cookies.clear()

    @contextmanager
    def _stream(self, method: str, path: str, **kwargs: Any) -> Iterator[httpx.Response]:
        """Stream an authenticated response without buffering downloads or event feeds.

        Args:
            method: HTTP method for the operation.
            path: API-relative path constructed by an endpoint object.
            **kwargs: HTTPX stream arguments, such as params or json.

        Yields:
            An open HTTPX response, closed when the context exits.

        Raises:
            RuntimeError: If the client has no authenticated session.
            httpx.HTTPError: For transport failures or unsuccessful responses.
        """
        if not self._token:
            raise RuntimeError("Log in before accessing resources")
        with self._http.stream(
            method,
            f"api/v1/{path}",
            headers={"Authorization": f"Bearer {self._token}"},
            **kwargs,
        ) as response:
            raise_for_api_status(response)
            yield response

    def logout(self) -> None:
        """Revoke the current server session and always forget local authentication.

        Raises:
            httpx.HTTPError: If revocation fails; local credentials are still cleared.
        """
        try:
            if self._token:
                self._request("DELETE", "auth/sessions/current")
        finally:
            self._clear_session()

    def close(self) -> None:
        """Close network resources and forget local credentials without server revocation."""
        self._clear_session()
        self._http.close()

    def __enter__(self) -> CoyoteClient:
        """Return this client for use in a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the transport when leaving a context, preserving any active exception."""
        self.close()
