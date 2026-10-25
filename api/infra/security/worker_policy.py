"""Fixed ingestion capability for the trusted deployment worker process."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class IngestWorkerIdentity(BaseModel):
    """Execution identity distinct from the submitter retained on durable ingest jobs."""

    model_config = ConfigDict(frozen=True)

    username: Literal["celery-ingest"] = "celery-ingest"
    fullname: str = "Ingestion worker"
    is_superuser: Literal[False] = False
    must_change_password: Literal[False] = False


class IngestWorkerPolicy:
    """Grant only durable ingestion execution to the host's fixed worker identity."""

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Deny clinical reads and administration, including caller-supplied role claims."""
        return (
            isinstance(user, IngestWorkerIdentity)
            and permission_id == "internal.ingest:manage"
            and not context
        )

    def scope_allowed(self, user: Any, context: dict[str, Any] | None) -> bool:
        """Deny sample-scoped operations for this job-execution capability."""
        return False
