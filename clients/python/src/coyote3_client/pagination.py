"""Bounded, explicit continuation for typed SDK collection pages."""

from collections.abc import Callable, Iterator
from typing import TypeVar

from pydantic import BaseModel

from coyote3_client.errors import ResponseValidationError
from coyote3_client.models import Page

ItemT = TypeVar("ItemT", bound=BaseModel)


def iter_pages(
    fetch: Callable[[int], Page[ItemT]], *, start_page: int = 1
) -> Iterator[Page[ItemT]]:
    """Fetch pages on demand until the server reports no continuation.

    Args:
        fetch: Function reading one numbered page without changing filters or sorting.
        start_page: First page to request, defaulting to one.

    Yields:
        Typed pages in server order; stopping iteration avoids subsequent requests.

    Raises:
        ValueError: If start_page is not a positive integer.
        ResponseValidationError: If pagination fails to advance or an empty page claims continuation.
    """
    if type(start_page) is not int or start_page < 1:
        raise ValueError("start_page must be a positive integer")
    page_number = start_page
    while True:
        page = fetch(page_number)
        if page.pagination.page != page_number:
            raise ResponseValidationError("Server pagination did not return the requested page")
        if page.pagination.has_next and not page.items:
            raise ResponseValidationError("An empty page cannot claim pagination continuation")
        yield page
        if not page.pagination.has_next:
            return
        page_number += 1
