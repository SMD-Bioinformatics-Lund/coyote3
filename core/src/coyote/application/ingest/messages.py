# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Allowlisted ingestion message names shared by publishers and worker hosts."""

from types import MappingProxyType

INGEST_TASK_NAMES = MappingProxyType(
    {
        "sample_bundle": "coyote_ingest.tasks.ingest_sample_bundle",
        "insert_document": "coyote_ingest.tasks.insert_collection_document",
        "insert_documents": "coyote_ingest.tasks.insert_collection_documents",
        "upsert_document": "coyote_ingest.tasks.upsert_collection_document",
    }
)
INGEST_DISPATCH_TASK = "coyote_ingest.tasks.dispatch_pending_jobs"
INGEST_WATCH_TASK = "coyote_ingest.tasks.ingest_watch_directory_once"


def ingest_task_name(kind: str) -> str:
    """Resolve the worker message name for a supported durable ingestion job.

    Args:
        kind: Logical job kind retained in the durable job repository.

    Returns:
        Message name understood by the ingestion service.

    Raises:
        KeyError: The job kind is not in the publication allowlist.
    """
    return INGEST_TASK_NAMES[kind]
