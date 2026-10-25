"""Project existing HTTP response envelopes into shared typed client pages."""

from typing import Any, TypeVar

from coyote3_client.errors import ResponseValidationError, parse_model
from coyote3_client.metadata import ResourceMetadata
from coyote3_client.models import FindingData, Page, PageInfo

ModelT = TypeVar("ModelT", bound=ResourceMetadata)


def metadata_rows_page(
    model: type[ModelT], payload: object, rows: object, pagination: object
) -> Page[ModelT]:
    """Validate rows and retain the server's complete envelope without accepting extra metadata.

    Args:
        model: Client-owned permitted metadata contract.
        payload: Complete response object retained for explicit envelope access.
        rows: Selected stream's row array.
        pagination: Selected stream's server pagination state.

    Returns:
        Typed permitted metadata with unchanged ordering and server pagination.

    Raises:
        ResponseValidationError: A row array, response object or pagination value is invalid.
    """
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ResponseValidationError("Resource list response must contain a row array")
    if not isinstance(payload, dict):
        raise ResponseValidationError("Resource list response must be an object")
    return Page[ModelT](
        items=[
            parse_model(model, {key: row[key] for key in model.model_fields if key in row})
            for row in rows
        ],
        pagination=parse_model(PageInfo, pagination),
        payload=payload,
    )


def sample_query(params: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Bind pagination to exactly one existing sample stream.

    Args:
        params: Query options using status, page and per_page.

    Returns:
        Wire query parameters and the selected live/done stream name.

    Raises:
        ValueError: Status is invalid or stream-specific pagination would be ambiguous.
    """
    status = params.get("status", "live")
    if status not in ("live", "done"):
        raise ValueError("Sample catalog status must be live or done")
    if any(key in params for key in ("live_page", "done_page", "live_per_page", "done_per_page")):
        raise ValueError("Use page and per_page for the selected sample stream")
    query = {**params, f"{status}_page": params.get("page", 1)}
    if "per_page" in params:
        query[f"{status}_per_page"] = params["per_page"]
    return query, status


def metadata_page(
    model: type[ModelT],
    payload: object,
    items_key: str,
    *,
    paginated: bool,
    sample_stream: str | None = None,
) -> Page[ModelT]:
    """Select an existing list envelope before applying the shared metadata projection.

    Args:
        model: Permitted metadata contract.
        payload: Server list response.
        items_key: Established array key for a nonsample collection.
        paginated: False for collections whose response contains all rows.
        sample_stream: live or done for independently paginated samples, otherwise None.

    Returns:
        A typed page retaining the original envelope.

    Raises:
        ResponseValidationError: The response or selected page violates the wire contract.
    """
    if not isinstance(payload, dict):
        raise ResponseValidationError("Resource list response must be an object")
    rows = payload.get(f"{sample_stream}_samples" if sample_stream else items_key)
    pagination = payload.get("pagination")
    if sample_stream:
        pagination = {
            key: payload.get(f"{sample_stream}_{key}") for key in ("page", "per_page", "total")
        }
        pagination["has_next"] = payload.get(f"has_next_{sample_stream}")
    elif not paginated and isinstance(rows, list):
        pagination = {
            "page": 1,
            "per_page": max(1, len(rows)),
            "total": len(rows),
            "has_next": False,
        }
    return metadata_rows_page(model, payload, rows, pagination)


def finding_page(payload: object, segment: str) -> Page[FindingData]:
    """Parse the server's modality-specific analysis page without clinical recalculation.

    Args:
        payload: Existing analysis list response including meta pagination.
        segment: small-variants, cnvs, fusions or translocations route segment.

    Returns:
        Findings in server order with the complete wire envelope.

    Raises:
        ResponseValidationError: The response or its finding rows are invalid.
    """
    if not isinstance(payload, dict):
        raise ResponseValidationError("Finding list response must be an object")
    if segment == "small-variants":
        sections = payload.get("display_sections_data")
        rows = sections.get("snvs") if isinstance(sections, dict) else None
    else:
        rows = payload.get(segment)
    return parse_model(
        Page[FindingData], {"items": rows, "pagination": payload.get("meta"), "payload": payload}
    )
