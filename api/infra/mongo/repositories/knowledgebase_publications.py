"""Record reference-maintenance publications in the knowledgebase release registry."""

from datetime import datetime, timezone
from typing import Any

from api.config.loaders.collections import load_collection_section


def record_reference_publication(
    database: Any, *, source: str, release: str, session: Any = None
) -> None:
    """Record a successfully installed or replaced reference release for notification delivery.

    Args:
        database: Knowledgebase database owning both reference records and versions.
        source: Stable reference collection or maintenance operation name.
        release: Producer release identifier, or bundled for the packaged baseline.
        session: Owning reference-write transaction when available; never another client's session.

    Notes:
        Replacing a release advances published_at, producing a distinct activity event.
        Call only after successful writes, and inside their transaction when one is used.
    """
    collection = database[
        load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
    ]
    collection.update_one(
        {"source": source, "release": release},
        {"$set": {"status": "active", "published_at": datetime.now(timezone.utc)}},
        upsert=True,
        session=session,
    )
