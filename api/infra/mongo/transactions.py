"""Required MongoDB transaction boundaries for related document mutations."""

from collections.abc import Callable
from typing import Any, TypeVar

from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from pymongo.write_concern import WriteConcern

T = TypeVar("T")


def run_transaction(client: Any, operation: Callable[[Any], T]) -> T:
    """Commit a retryable database-only operation without falling back to plain writes.

    The driver may invoke the callback more than once. File, network, notification,
    and cache side effects must run after this function returns successfully.
    """
    with client.start_session() as session:
        return session.with_transaction(
            operation,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority", j=True),
            read_preference=ReadPreference.PRIMARY,
        )
